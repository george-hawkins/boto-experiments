Boto3 renderer
==============

Render [Blender](https://www.blender.org/) animations (using Cycles) on AWS.

The following assumes some familiarity with AWS - see my [notes elsewhere](https://github.com/george-hawkins/aws-notes) on getting started with AWS.

Running jobs from the command line
----------------------------------

```
$ source venv/bin/activate
(venv) $ python run_manager.py --ec2-instances 8 --start=1 --end=16 --samples=64 --enable-motion-blur my-blender-file.blend
```

Setup
-----

Create a Python venv:

```
$ python3 -m venv venv
$ source venv/bin/activate
(venv) $ pip install --upgrade pip
```

Install boto3 and the [boto3-stubs](https://pypi.org/project/boto3-stubs/) type annotations:

```
(venv) $ pip install boto3 'boto3-stubs[essential,logs]'
```

Note: the stubs won't pull in `boto3` as a dependency - you have to install both `boto3` and the stubs.


Roles
-----

See [`create-role.md`](docs/create-role.md).

Security groups
---------------

See [`create-security-groups.md`](docs/create-security-group.md)

Python scripts with main
------------------------

* `run_manager`
* `run_worker`
* `create_file_store` - run once and store result in xxx and upload a version of Blender there and store that also in xxx. 
* `clean_up.py`

Running the worker locally
--------------------------

Stop `run_manager` at the point where it's created all the AWS resources, but before it's launched the EC2 instances.

TODO: fill-in.

Spot pricing
------------

Point to section in https://github.com/george-hawkins/aws-notes / more-aws-notes.md

Notes
-----

See [`boto3-notes.md`](docs/boto3-notes.md).