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

    # Check if the invocation comes from API Gateway or not
    payload = json.loads(event["body"]) if "body" in event else event

    # Does not seem like paper2remarkable is set up as a Python library, so we pass in
    # parameters by simulating that we're calling it from the command-line
    args = [
        *(["--verbose"] if payload.get("verbose", True) else []),
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

    credentials_file = "/tmp/rmapi.conf"
    with open(credentials_file, "w") as f:
        f.write(
            f"""
usertoken: {os.environ['RMAPI_USER_TOKEN']}
devicetoken: {os.environ['RMAPI_DEVICE_TOKEN']}
"""
        )
    logger.debug("Stored rmapi credentials in '%s'", credentials_file)
    os.environ["RMAPI_CONFIG"] = credentials_file

    successes = {}
    failures = {}
    
    # if we have a "input" value (zapier friendly) append to inputs
    if "input" in payload:
        if not "inputs" in payload:
            payload["inputs"] = []
        payload["inputs"].append(payload["input"])
    for file in payload["inputs"]:
        # We get some weird errors at times:
        # `[Errno 2] No such file or directory`
        # that seem to stem from inability to start a shell:
        # `shell-init: error retrieving current directory: getcwd: cannot access parent directories: No such file or directory`
        # This is most likely due to reuse of Lambda execution contexts,
        # as the error does not seem to occur on clean executions.
        # Only processing a single input at a time and changing the
        # directory to a known directory seems to fix it.
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
        if return_code == 0:
            successes[file] = output
        else:
            failures[file] = output
            logger.warn("paper2remarkable command had non-zero exit")

    status_code = 200 if len(failures) == 0 else 500
    response = {"statusCode": status_code}
    return response
