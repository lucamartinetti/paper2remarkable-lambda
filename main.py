#!/usr/bin/env python
#
# Copyright (C) 2020 Erlend Ekern <dev@ekern.me>
#
# Distributed under terms of the MIT license.

"""
A Lambda wrapper for paper2remarkable.
"""

import json
import os
import logging
import selectors
import signal
import subprocess
import base64
import uuid
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def timeout_handler(signal_number, stack_frame):
    """Raise exception if we are close to Lambda timeout limit"""
    logger.warn("Lambda is about to time out")
    raise Exception("Time exceeded")


signal.signal(signal.SIGALRM, timeout_handler)


def lambda_handler(event, context):
    signal.alarm((context.get_remaining_time_in_millis() // 1000) - 2)
    logger.debug("Lambda triggered with event '%s'", event)

    payload = event["queryStringParameters"]
    # Does not seem like paper2remarkable is set up as a Python library, so we pass in
    # parameters by simulating that we're calling it from the command-line


    tmp_file_name = uuid.uuid4()
    args = [
        *(["--no-upload"]),
        *(["--filename", f"/tmp/{tmp_file_name}.pdf"]),
        *(["--verbose"]),
        *(["--blank"] if payload.get("blank", False) else []),
        *(["--center"] if payload.get("center", False) else []),
        *(["--right"] if payload.get("right", False) else []),
        *(["--no-crop"] if payload.get("disable_cropping", False) else []),
        *(
            ["--remarkable-path", payload["remarkable_path"]]
            if payload.get("remarkable_path", None)
            else []
        ),
    ]

    file = payload["url"]
    logger.debug("Running paper2remarkable for file '%s'", file)
    os.chdir("/tmp")
    proc = subprocess.Popen(
        ["p2r"] + args + [file], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ)
    sel.register(proc.stderr, selectors.EVENT_READ)
    output = {"stdout": "", "stderr": ""}
    # Continuously log stdout and stderr while
    # process is running
    while proc.poll() is None:
        for key, _ in sel.select():
            data = key.fileobj.read1().decode()
            if not data:
                continue
            if key.fileobj is proc.stdout:
                output["stdout"] += data
                logger.debug(data)
            else:
                output["stderr"] += data
                logger.error(data)
    return_code = proc.returncode

    if return_code != 0:
        logger.warn("paper2remarkable command had non-zero exit")

    if return_code != 0:
        raise Exception()
    
    #there is be a bug in p2r. The output file is named "foo_.pdf" instead of "foo.pdf"
    tmp_file_path = f"/tmp/{tmp_file_name}_.pdf" 
    with open( tmp_file_path, "rb") as f:
        b = base64.b64encode(f.read()).decode("utf-8")

    response = {
        "statusCode": 200,
        "headers": {
            'Content-type' : 'application/pdf'
        },
        "body": b,
        "isBase64Encoded": True
    }
    os.remove(tmp_file_path)

    return response