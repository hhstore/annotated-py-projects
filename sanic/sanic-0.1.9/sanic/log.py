#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging

#
# 日志选项配置:
#   - 日志格式
#
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s: %(levelname)s: %(message)s")

#
# 日志记录器:
#
log = logging.getLogger(__name__)
