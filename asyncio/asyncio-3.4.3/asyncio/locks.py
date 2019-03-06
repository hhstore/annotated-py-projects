#!/usr/bin/env python
# -*- coding: utf-8 -*-


"""Synchronization primitives."""

__all__ = ['Lock', 'Event', 'Condition', 'Semaphore', 'BoundedSemaphore']

import collections       # 数据类型: 双端队列, deque是为了高效实现插入和删除操作的双向列表，适合用于队列和栈

from . import events
from . import futures
from .coroutines import coroutine


#########################################
#             同步原语:
# 说明:
#   - 几种同步机制:
#       - 锁(lock)
#       - 事件(event)
#       - 条件原语(condition)
#       - 信号量(semaphore)
#
#########################################

# 上下文管理:
class _ContextManager:
    """Context manager.

    This enables the following idiom for acquiring and releasing a
    lock around a block:

        with (yield from lock):
            <block>

    while failing loudly when accidentally using:

        with lock:
            <block>
    """

    def __init__(self, lock):
        self._lock = lock

    def __enter__(self):
        # We have no use for the "as ..."  clause in the with
        # statement for locks.
        return None

    def __exit__(self, *args):
        try:
            self._lock.release()         # 释放锁
        finally:
            self._lock = None  # Crudely prevent reuse.


# 锁
class Lock:
    """Primitive lock objects.

    A primitive lock is a synchronization primitive that is not owned
    by a particular coroutine when locked.  A primitive lock is in one
    of two states, 'locked' or 'unlocked'.

    It is created in the unlocked state.  It has two basic methods,
    acquire() and release().  When the state is unlocked, acquire()
    changes the state to locked and returns immediately.  When the
    state is locked, acquire() blocks until a call to release() in
    another coroutine changes it to unlocked, then the acquire() call
    resets it to locked and returns.  The release() method should only
    be called in the locked state; it changes the state to unlocked
    and returns immediately.  If an attempt is made to release an
    unlocked lock, a RuntimeError will be raised.

    When more than one coroutine is blocked in acquire() waiting for
    the state to turn to unlocked, only one coroutine proceeds when a
    release() call resets the state to unlocked; first coroutine which
    is blocked in acquire() is being processed.

    acquire() is a coroutine and should be called with 'yield from'.

    Locks also support the context management protocol.  '(yield from lock)'
    should be used as context manager expression.

    Usage:

        lock = Lock()
        ...
        yield from lock
        try:
            ...
        finally:
            lock.release()

    Context manager usage:

        lock = Lock()
        ...
        with (yield from lock):
             ...

    Lock objects can be tested for locking state:

        if not lock.locked():
           yield from lock
        else:
           # lock is acquired
           ...

    """

    def __init__(self, *, loop=None):
        self._waiters = collections.deque()     # collections.deque: 双端队列，可以快速的从另外一侧追加和推出对象
        self._locked = False                    # 锁状态

        if loop is not None:
            self._loop = loop
        else:
            self._loop = events.get_event_loop()

    def __repr__(self):
        res = super().__repr__()
        extra = 'locked' if self._locked else 'unlocked'
        if self._waiters:
            extra = '{},waiters:{}'.format(extra, len(self._waiters))
        return '<{} [{}]>'.format(res[1:-1], extra)

    #
    # 锁状态:
    #
    def locked(self):
        """Return True if lock is acquired."""
        return self._locked

    #
    # 申请锁:
    #
    @coroutine
    def acquire(self):
        """Acquire a lock.

        This method blocks until the lock is unlocked, then sets it to
        locked and returns True.
        """
        if not self._waiters and not self._locked:     # 队列不空
            self._locked = True
            return True

        #
        # future 对象
        #
        fut = futures.Future(loop=self._loop)
        self._waiters.append(fut)        # 入队操作

        try:
            yield from fut               # 异步返回 future 对象
            self._locked = True
            return True
        finally:
            self._waiters.remove(fut)    # 出队操作

    #
    # 释放锁:
    #
    def release(self):
        """Release a lock.

        When the lock is locked, reset it to unlocked, and return.
        If any other coroutines are blocked waiting for the lock to become
        unlocked, allow exactly one of them to proceed.

        When invoked on an unlocked lock, a RuntimeError is raised.

        There is no return value.
        """
        if self._locked:
            self._locked = False
            # Wake up the first waiter who isn't cancelled.
            for fut in self._waiters:        # 遍历双端队列
                if not fut.done():           # 未完成
                    fut.set_result(True)
                    break
        else:
            raise RuntimeError('Lock is not acquired.')

    def __enter__(self):
        raise RuntimeError(
            '"yield from" should be used as context manager expression')

    def __exit__(self, *args):
        # This must exist because __enter__ exists, even though that
        # always raises; that's how the with-statement works.
        pass

    #
    # 迭代:
    #   - 异步返回
    #   - 返回上下文管理
    #
    def __iter__(self):
        # This is not a coroutine.  It is meant to enable the idiom:
        #
        #     with (yield from lock):
        #         <block>
        #
        # as an alternative to:
        #
        #     yield from lock.acquire()
        #     try:
        #         <block>
        #     finally:
        #         lock.release()
        yield from self.acquire()          # 异步返回
        return _ContextManager(self)


# 事件:
class Event:
    """Asynchronous equivalent to threading.Event.

    Class implementing event objects. An event manages a flag that can be set
    to true with the set() method and reset to false with the clear() method.
    The wait() method blocks until the flag is true. The flag is initially
    false.
    """

    def __init__(self, *, loop=None):
        self._waiters = collections.deque()            # 双端队列
        self._value = False

        if loop is not None:
            self._loop = loop
        else:
            self._loop = events.get_event_loop()

    def __repr__(self):
        res = super().__repr__()
        extra = 'set' if self._value else 'unset'
        if self._waiters:
            extra = '{},waiters:{}'.format(extra, len(self._waiters))
        return '<{} [{}]>'.format(res[1:-1], extra)

    def is_set(self):
        """Return True if and only if the internal flag is true."""
        return self._value

    #
    # 设置:
    #
    def set(self):
        """Set the internal flag to true. All coroutines waiting for it to
        become true are awakened. Coroutine that call wait() once the flag is
        true will not block at all.
        """
        if not self._value:
            self._value = True

            for fut in self._waiters:     # 遍历双端队列
                if not fut.done():        # 未完成
                    fut.set_result(True)

    #
    # 清理:
    #
    def clear(self):
        """Reset the internal flag to false. Subsequently, coroutines calling
        wait() will block until set() is called to set the internal flag
        to true again."""
        self._value = False

    @coroutine
    def wait(self):
        """Block until the internal flag is true.

        If the internal flag is true on entry, return True
        immediately.  Otherwise, block until another coroutine calls
        set() to set the flag to true, then return True.
        """
        if self._value:
            return True

        fut = futures.Future(loop=self._loop)     # future 对象
        self._waiters.append(fut)                 # 入队

        try:
            yield from fut                        # 异步返回
            return True
        finally:
            self._waiters.remove(fut)             # 出队


#
# 条件原语:
#   - 依赖 Lock 实现
#
class Condition:
    """Asynchronous equivalent to threading.Condition.

    This class implements condition variable objects. A condition variable
    allows one or more coroutines to wait until they are notified by another
    coroutine.

    A new Lock object is created and used as the underlying lock.
    """

    def __init__(self, lock=None, *, loop=None):
        if loop is not None:
            self._loop = loop
        else:
            self._loop = events.get_event_loop()

        if lock is None:
            lock = Lock(loop=self._loop)      # 锁
        elif lock._loop is not self._loop:
            raise ValueError("loop argument must agree with lock")

        self._lock = lock
        # Export the lock's locked(), acquire() and release() methods.
        self.locked = lock.locked
        self.acquire = lock.acquire    # 申请锁
        self.release = lock.release    # 释放锁

        self._waiters = collections.deque()     # 双端队列

    def __repr__(self):
        res = super().__repr__()
        extra = 'locked' if self.locked() else 'unlocked'
        if self._waiters:
            extra = '{},waiters:{}'.format(extra, len(self._waiters))
        return '<{} [{}]>'.format(res[1:-1], extra)

    @coroutine
    def wait(self):
        """Wait until notified.

        If the calling coroutine has not acquired the lock when this
        method is called, a RuntimeError is raised.

        This method releases the underlying lock, and then blocks
        until it is awakened by a notify() or notify_all() call for
        the same condition variable in another coroutine.  Once
        awakened, it re-acquires the lock and returns True.
        """
        if not self.locked():
            raise RuntimeError('cannot wait on un-acquired lock')

        self.release()                  # 释放锁
        try:
            fut = futures.Future(loop=self._loop)    # future 对象
            self._waiters.append(fut)                # 入队
            try:
                yield from fut                       # 异步返回
                return True
            finally:
                self._waiters.remove(fut)            # 出队

        finally:
            yield from self.acquire()    # 申请锁

    @coroutine
    def wait_for(self, predicate):
        """Wait until a predicate becomes true.

        The predicate should be a callable which result will be
        interpreted as a boolean value.  The final predicate value is
        the return value.
        """
        result = predicate()
        while not result:
            yield from self.wait()    # 异步返回
            result = predicate()
        return result

    def notify(self, n=1):
        """By default, wake up one coroutine waiting on this condition, if any.
        If the calling coroutine has not acquired the lock when this method
        is called, a RuntimeError is raised.

        This method wakes up at most n of the coroutines waiting for the
        condition variable; it is a no-op if no coroutines are waiting.

        Note: an awakened coroutine does not actually return from its
        wait() call until it can reacquire the lock. Since notify() does
        not release the lock, its caller should.
        """
        if not self.locked():
            raise RuntimeError('cannot notify on un-acquired lock')

        idx = 0
        for fut in self._waiters:    # 遍历双端队列
            if idx >= n:
                break

            if not fut.done():
                idx += 1
                fut.set_result(False)

    def notify_all(self):
        """Wake up all threads waiting on this condition. This method acts
        like notify(), but wakes up all waiting threads instead of one. If the
        calling thread has not acquired the lock when this method is called,
        a RuntimeError is raised.
        """
        self.notify(len(self._waiters))

    def __enter__(self):
        raise RuntimeError(
            '"yield from" should be used as context manager expression')

    def __exit__(self, *args):
        pass

    def __iter__(self):
        # See comment in Lock.__iter__().
        yield from self.acquire()      # 申请锁
        return _ContextManager(self)   # 上下文管理


#
# 信号量机制:
#
class Semaphore:
    """A Semaphore implementation.

    A semaphore manages an internal counter which is decremented by each
    acquire() call and incremented by each release() call. The counter
    can never go below zero; when acquire() finds that it is zero, it blocks,
    waiting until some other thread calls release().

    Semaphores also support the context management protocol.

    The optional argument gives the initial value for the internal
    counter; it defaults to 1. If the value given is less than 0,
    ValueError is raised.
    """

    def __init__(self, value=1, *, loop=None):
        if value < 0:
            raise ValueError("Semaphore initial value must be >= 0")
        self._value = value
        self._waiters = collections.deque()    # 双端队列

        if loop is not None:
            self._loop = loop
        else:
            self._loop = events.get_event_loop()

    def __repr__(self):
        res = super().__repr__()
        extra = 'locked' if self.locked() else 'unlocked,value:{}'.format(
            self._value)
        if self._waiters:
            extra = '{},waiters:{}'.format(extra, len(self._waiters))
        return '<{} [{}]>'.format(res[1:-1], extra)

    def locked(self):
        """Returns True if semaphore can not be acquired immediately."""
        return self._value == 0

    #
    # 申请:
    #
    @coroutine
    def acquire(self):
        """Acquire a semaphore.

        If the internal counter is larger than zero on entry,
        decrement it by one and return True immediately.  If it is
        zero on entry, block, waiting until some other coroutine has
        called release() to make it larger than 0, and then return
        True.
        """
        if not self._waiters and self._value > 0:
            self._value -= 1
            return True

        fut = futures.Future(loop=self._loop)     # future 对象
        self._waiters.append(fut)        # 入队

        try:
            yield from fut               # 异步返回
            self._value -= 1
            return True
        finally:
            self._waiters.remove(fut)    # 出队

    #
    # 释放:
    #
    def release(self):
        """Release a semaphore, incrementing the internal counter by one.
        When it was zero on entry and another coroutine is waiting for it to
        become larger than zero again, wake up that coroutine.
        """
        self._value += 1
        for waiter in self._waiters:      # 遍历双端队列
            if not waiter.done():         # 未完成
                waiter.set_result(True)
                break

    def __enter__(self):
        raise RuntimeError(
            '"yield from" should be used as context manager expression')

    def __exit__(self, *args):
        pass

    #
    # 迭代:
    #
    def __iter__(self):
        # See comment in Lock.__iter__().
        yield from self.acquire()          # 异步返回
        return _ContextManager(self)       # 上下文管理


#
# 信号量:
#
class BoundedSemaphore(Semaphore):
    """A bounded semaphore implementation.

    This raises ValueError in release() if it would increase the value
    above the initial value.
    """

    def __init__(self, value=1, *, loop=None):
        self._bound_value = value
        super().__init__(value, loop=loop)

    #
    # 释放:
    #
    def release(self):
        if self._value >= self._bound_value:
            raise ValueError('BoundedSemaphore released too many times')
        super().release()    # 释放
