Boto3 renderer
==============

Render [Blender](https://www.blender.org/) animations (using Cycles) on AWS spot instances.

The following assumes some familiarity with AWS, that you already have an AWS account and have the [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/) set up. See my [notes](https://github.com/george-hawkins/aws-notes) elsewhere on getting started with AWS.

Running render jobs from the command line
-----------------------------------------

The following command will start eight EC2 spot instances to render frames 1 to 120 of `foo.blend` using 512 samples:

```
(venv) $ python run_manager.py --ec2-instances 8 --start=1 --end=120 --samples=512 foo.blend
```

The `.blend` file is automatically packed to ensure that all referenced resources (textures etc.) are also included. The type of instance, e.g. a `g4dn.xlarge` (with an Nvidia [T4 GPU](https://www.nvidia.com/en-us/data-center/tesla-t4/)), is configured in the [`settings.ini`](settings.ini) file.

Don't forget to activate the necessary Python venv (see below) before running commands like the one above:

```
$ source venv/bin/activate
```

Command line options
--------------------

The `run_manager.py` script that creates and manages the render job takes various arguments. The only mandatory one is the `.blend` file to render. If you don't e.g. specify a start and end frame then the values already set in the `.blend` file are used.

Arguments:

* `--blender-home` - the home directory of you local Blender installation, e.g. `~/blender-3.2.0-linux-x64`.
* `--start`,`--end` and `--step` - the start and end frame of the animation and the step between frames (usually one).
* `--frames` - alternatively, a comma separated list of frames can be specified, e.g. `2, 3, 5, 7, 11, 13, 17`.
* `--samples` - the number of samples per pixel.
* `--ec2-instances` - the number of EC2 instances to start.
* `--disable-interactive` - disable the prompt where the details of the job can be double-checked before the EC2 instances are started.
* `--enable-motion-blur` and `--disable-motion-blur` - enable or disable motion blur.

Your local installation of Blender is used to pack the `.blend` file and determine the settings it contains for things like motion blur.

If you've been checking individual frames locally, you may have turned off motion blur. However, for an animation, motion blur should usually be enabled - so the script will exit if it finds this is not the case for the `.blend` file. This behavior can be overridden by explicitly specifying `--disable-motion-blur`. Or motion blur can be turned on with `--enable-motion-blur`.

Settings
--------

Various other settings must be configured in [`settings.ini`](settings.ini):

* `blender_home` - a default to be used if `--blender-home` is not specified as a command line argument.
* `instance_count` - a default to be used if `--ec2-instances` is not specified as a command line argument.
* `instance_type` - the EC2 instance type to use, e.g. `g4dn.xlarge`.
* `image_name_pattern` - the pattern to use to determine the image to run on the instances, e.g. `amzn2-ami-graphics-hvm-*`.

You also have to specify the `security_group_name` and `iam_instance_profile` that are used by the EC2 instances - these are covered later.

And you have to specify a `file_store` bucket and a `blender_archive` that's stored there - these are also covered later.

A pattern is used for the image name so that the latest available version of an image is always used. E.g. if using the [Amazon Linux 2 AMI with NVIDIA TESLA GPU Driver](https://aws.amazon.com/marketplace/pp/prodview-64e4rx3h733ru), the pattern `amzn2-ami-graphics-hvm-*` always maps to the latest version rather than a specific version, e.g. the `2.0.20220606.1` one, that swiftly becomes stale.

Note: as the [G5 instances](https://aws.amazon.com/ec2/instance-types/g5/) become more widely available, it will make sense to switch from `g4dn.xlarge` to `g5.xlarge`.

Setup
-----

The basic setup is very simple, first clone this repo:

```
$ git clone git@github.com:george-hawkins/boto3-renderer.git
$ cd boto3-renderer
```

Create a Python venv:

```
$ python3 -m venv venv
$ source venv/bin/activate
(venv) $ pip install --upgrade pip
```

<!-- 3.8 introduced Path.unlink(missing_ok=True) -->
The local Python version must be at least 3.8 (released late 2019). This can be checked with:

```
(venv) $ python --version
Python 3.9.5
```

Install [`boto3`](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html) and the [`boto3-stubs`](https://pypi.org/project/boto3-stubs/) type annotations:

```
(venv) $ pip install boto3 'boto3-stubs[essential,logs]'
```

Note: the stubs won't pull in `boto3` as a dependency - you have to install both `boto3` and the stubs.

Now, you just need to set up a file store and the necessary role profile to be used by the EC2 instances.

File store setup
----------------

The EC2 instances need to download an archive containing Blender at startup so, they can render the frames of the animation. This archive is about 170MiB and it is far quicker to download it from within AWS than to pull it each time from the public internet.

So, an S3 bucket (that's used as a long-lived file store for this archive) needs to be created and an archive of Blender needs to be uploaded there.

To create the S3 bucket, just run `create_file_store.py`:

```
(venv) $ python create_file_store.py 
Created s3://render-job-file-store-b4867a49-d22c-4084-ba72-8e760e3a2722
To copy files there use 'aws s3 cp <filename> s3://render-job-file-store-b4867a49-d22c-4084-ba72-8e760e3a2722'
```

Then download a version of Blender for Linux from the [Blender site](https://www.blender.org/download/) and upload it to the just created file store bucket:

```
$ aws s3 cp ~/Downloads/blender-3.2.0-linux-x64.tar.xz s3://render-job-file-store-b4867a49-d22c-4084-ba72-8e760e3a2722
```

Then edit [`settings.ini`](settings.ini) and use the file store bucket name as the value for `file_store` and the Blender archive name as the `blender_archive` value.

That's it - storing the Blender archive permanently like this costs almost nothing - the cost per GiB per year is about $0.30.

### Updating Blender on the file store

Later, if you download a newer version of Blender, you can update it on the file store as follows.

Determine the file store S3 URI and delete the current archive there:

```
$ fgrep file_store: settings.ini
file_store: s3://file-store-dcede0e0-aec4-4920-9532-c89a3a151af2
$ aws s3 ls s3://file-store-dcede0e0-aec4-4920-9532-c89a3a151af2
2022-06-04 17:50:32  187294308 blender-3.1.2-linux-x64.tar.xz
$ aws s3 rm s3://file-store-dcede0e0-aec4-4920-9532-c89a3a151af2/blender-3.1.2-linux-x64.tar.xz
```

Copy the new archive to the file store bucket:

```
$ aws s3 cp ~/Downloads/blender-3.2.0-linux-x64.tar.xz s3://file-store-dcede0e0-aec4-4920-9532-c89a3a151af2
```

Then edit `settings.ini` and change the value of `blender_archive` to match the name of the just uploaded archive.

Role and security group
-----------------------

The EC2 instances need an IAM role and profile and an EC2 security group. To create these you just need to go through the short opening **TLDR;** section in [`create-role.md`](docs/create-role.md) and [`create-security-groups.md`](docs/create-security-group.md).

Note: the created security group tries to make the EC2 instances as secure as possible - it doesn't allow any incoming traffic so, you won't be able to ssh to these instances (but of course, they can still be terminated via e.g. [terminates-instances](https://awscli.amazonaws.com/v2/documentation/api/latest/reference/ec2/terminate-instances.html)).

Cleaning up
-----------

If a render job is left to run to completion then it will delete all resources, such as S3 buckets, that were created during the course of the job.

However, if you've been experimenting and killed things off before completion, you can easily delete any resources that have been left hanging around using `clean_up.py`:

```
(venv) $ python clean_up.py 
Deleted log group render-job-log_group-7238af0c-fc26-49a7-b336-ca3a03fee08d
Deleted bucket render-job-bucket-273f27ec-f678-4b54-b95f-f5ae1fc3fcc2
Deleted bucket render-job-bucket-7238af0c-fc26-49a7-b336-ca3a03fee08d
Deleting table render-job-dynamodb-6e78c43f-bb85-41e6-9fba-3e793de11597...
table deletion took 20.10s
Deleted table render-job-dynamodb-6e78c43f-bb85-41e6-9fba-3e793de11597
Deleting table render-job-dynamodb-7238af0c-fc26-49a7-b336-ca3a03fee08d...
table deletion took 20.08s
Deleted table render-job-dynamodb-7238af0c-fc26-49a7-b336-ca3a03fee08d
```

This will **not** terminate any EC2 instances you have running. To reassure yourself that you have no running EC2 instances (irrespective of whether they're render job related or not), run `running_instances.py`:

```
(venv) $ python running_instances.py
There are currently 0 non-terminated EC2 instances
```

If there are running instances, and you want to terminate them, first find them:

```
$ aws ec2 describe-instances --query 'Reservations[*].Instances[*].[InstanceId, State.Name]' --o text
i-06bfb2ebff8962544     running
i-0b5b95967aa51916a     running
```

Then terminate all the ones that aren't already listed as being in state `shutting-down` or `terminated`:

```
$ aws ec2 terminate-instances --instance-ids i-06bfb2ebff8962544 i-0b5b95967aa51916a
```

You can check that they really have terminated with the same `describe-instances` command as above - it typically takes 30s to a minute for the instances to reach `terminated` state.

Summary of main Python scripts
------------------------------

These are the main scripts here:

* `run_manager.py` - the script used to create a render job, launch the EC2 instances involved, monitor them and terminate them (once the job is completed), and download the results.
* `run_worker.py` - the main script that runs on the EC2 instances and manages the rendering of individual frames.
* `create_file_store` - the script that's run once to create a file store to which a version of Blender is uploaded (and then used by the EC2 instances).
* `clean_up.py` - a script that can be run to delete any render related resources that may have become orphaned while experimenting with things.
* `running_instances.py` - reports the number of EC2 instances that are not in terminated state.

Running the worker locally
--------------------------

If you want to experiment with things and see the rendering happening locally rather than on an EC2 instance, you can stop the job creation process at the point where it asks you if you want to start the EC2 instances and then run the render work locally.

First create everything needed for the render job:

```
(venv) $ python run_manager.py --ec2-instances 8 --start=1 --end=16 --samples=64 --enable-motion-blur ~/.../foo.blend
Created log group render-job-log_group-b4cde934-3726-44ad-8e57-9555d3cdbfc9
Packed the .blend file
Uploaded job files to s3://render-job-bucket-b4cde934-3726-44ad-8e57-9555d3cdbfc9
Creating table render-job-dynamodb-b4cde934-3726-44ad-8e57-9555d3cdbfc9...
table creation took 20.11s
Created DynamoDB table render-job-dynamodb-b4cde934-3726-44ad-8e57-9555d3cdbfc9
instance count = 8, .blend file = ../blender-projects/foo.blend, frames = 1 to 16 inclusive, samples = 64 and motion_blur = True
Launch workers? [y/n] n
Clean up? [Y/n] n
```

Above I answered `n` to both the "launch workers?" and "clean up?" questions.

The above process will have created a number of files that would have usually been deleted at the end of the rendering process. The important one for running the remainder of the work locally, rather than on EC2 instances, is `user_data`. It'll contain something like this:

```
(venv) $ cat user_data 
#!/bin/bash

# The initial PWD is /.
home=/var/tmp/job_home
mkdir $home
cd $home

aws s3 cp s3://render-job-bucket-b4cde934-3726-44ad-8e57-9555d3cdbfc9 . --recursive
chmod u+x start_job 
./start_job

sudo poweroff
```

It's just the middle block that's interesting, i.e. where things are copied from an S3 bucket and the `start_job` script is run.

Let's do that locally instead:

```
(venv) $ mkdir job_home
(venv) $ cd job_home
(venv) $ aws s3 cp s3://render-job-bucket-b4cde934-3726-44ad-8e57-9555d3cdbfc9 . --recursive
download: s3://render-job-bucket-b4cde934-3726-44ad-8e57-9555d3cdbfc9/boto_basics.py to ./boto_basics.py
...
download: s3://render-job-bucket-b4cde934-3726-44ad-8e57-9555d3cdbfc9/packed.blend to ./packed.blend
(venv) $ chmod u+x start_job 
(venv) $ ./start_job
download: s3://file-store-dcede0e0-aec4-4920-9532-c89a3a151af2/blender-3.1.2-linux-x64.tar.xz to ./blender-3.1.2-linux-x64.tar.xz
...
Successfully installed boto3-1.24.12 boto3-stubs-1.24.12 botocore-1.27.12 botocore-stubs-1.27.12 jmespath-1.0.1 mypy-boto3-cloudformation-1.24.0 mypy-boto3-dynamodb-1.24.12 mypy-boto3-ec2-1.24.0 mypy-boto3-lambda-1.24.0 mypy-boto3-logs-1.24.0 mypy-boto3-rds-1.24.0 mypy-boto3-s3-1.24.0 mypy-boto3-sqs-1.24.0 python-dateutil-2.8.2 s3transfer-0.6.0 six-1.16.0 typing-extensions-4.2.0 urllib3-1.26.9
Blender 3.1.2 (hash cc66d1020c3b built 2022-03-31 23:36:08)
...
Fra:1 Mem:34.32M (Peak 46.72M) | Time:00:00.14 | Mem:0.00M, Peak:0.00M | Scene, ViewLayer | Initializing
...
Saved: '/home/joebloggs/git/boto3-renderer/job_home/frame-0001.png'
...
Blender quit
...
Saved: '/home/joebloggs/git/boto3-renderer/job_home/frame-0002.png'
...
```

Eventually, it'll complete all the frames in the job. Note: Blender quits and is restarted after each frame - this is expected and doesn't add much overhead.

The results end up in the same bucket that you see in the `user_data` script. So you can download them like so:

```
(venv) $ aws s3 cp --recursive s3://render-job-bucket-b4cde934-3726-44ad-8e57-9555d3cdbfc9/frames frames
download: s3://render-job-bucket-b4cde934-3726-44ad-8e57-9555d3cdbfc9/frames/frame-0001.png to frames/frame-0001.png
...
download: s3://render-job-bucket-b4cde934-3726-44ad-8e57-9555d3cdbfc9/frames/frame-0016.png to frames/frame-0016.png
```

You'll now have to manually clean up:

```
(venv) $ cd ..
(venv) $ rm -r job_home
(venv) $ rm packed.blend* start_job user_data
(venv) $ python clean_up.py 
Deleted log group render-job-log_group-b4cde934-3726-44ad-8e57-9555d3cdbfc9
...
```

Spot pricing
------------

Determining how much a render job is going to cost isn't trivial.

The `g4dn.xlarge` instances, that I'm currently using, have an Nvidia T4 GPU. Nvidia produce data center specific GPUs, like the T4, that are hard to compare with the retail GPUs that you find in desktops or laptops because the benchmark sites typically have zero or very poor coverage for data center GPUs.

It turns out that a T4 has about 80% the performance of an RTX 2060 desktop GPU or about 40% the performance of an RTX 3090.

If you know how your graphics card compares to the RTX 2060 (e.g. see the PassMark graphics card [benchmarks page](https://www.videocardbenchmark.net/GPU_mega_page.html)) and how long it takes your graphics card to render a frame of your animation then you can work from there to a guesstimate for how long it'll take a single T4 GPU to render a frame.

Then you can work out the total time to render your animation on a `g4dn.xlarge` instance and then check the current spot prices for `g4dn.xlarge` images in your region:

```
$ aws ec2 describe-spot-price-history --start-time=$(date +%s) --product-descriptions='Linux/UNIX' --instance-types g4dn.xlarge
{
    "SpotPriceHistory": [
        {
            "AvailabilityZone": "eu-central-1c",
            "InstanceType": "g4dn.xlarge",
            "ProductDescription": "Linux/UNIX",
            "SpotPrice": "0.197400",
            "Timestamp": "2022-06-10T21:56:38+00:00"
        },
        {
            "AvailabilityZone": "eu-central-1b",
            "InstanceType": "g4dn.xlarge",
            "ProductDescription": "Linux/UNIX",
            "SpotPrice": "0.197400",
            "Timestamp": "2022-06-10T19:46:42+00:00"
        },
        {
            "AvailabilityZone": "eu-central-1a",
            "InstanceType": "g4dn.xlarge",
            "ProductDescription": "Linux/UNIX",
            "SpotPrice": "0.197400",
            "Timestamp": "2022-06-10T19:46:42+00:00"
        }
    ]
}
```

Above, you can see that the current spot price is $0.1974 per hour - under normal circumstances this is exactly 30% of the on-demand price (30% seems to be a lower bound - AWS don't seem to let the spot price fall below this).

Note: the `Timestamp` values may be up to a day old - the prices typically don't change very often.

So if you estimate that your render will take 16 hours using a single T4 GPU then the price will be 16 * $0.1974, i.e. $3.16.

If, rather than a single EC2 instance, you spin up e.g. 32 instances then the render time will drop from 16 hours to 30 minutes. However, you have to factor in some additional costs due to the time those instances take to startup and shutdown - typically this will be less than 2 minutes per instance. So for 32 instances, this is about an additional hour of instance time, i.e. around ~$0.20.

For more on spot pricing, see my notes [here](https://github.com/george-hawkins/aws-notes/blob/master/more-aws-notes.md#spot-pricing).

Debugging worker failure
------------------------

If you've made a change to e.g. `templates/user_data` and the workers start failing, it can be hard to see what's going on.

To debug this situation:

* Comment out `poweroff` in [`templates/user_data`](templates/user_data).
* Uncomment the `security_group` and `key_name` entries in [`settings.ini`](settings.ini) that point to a security group that allows incoming ssh connections and to the name of the key-pair to use for such connections (and make sure the entries are valid for your setup and that e.g. the source IP address specified in the security group is still valid).
* Start a job with a single instance, like so:

```
$ python run_manager.py --ec2-instances 1 foo.blend
```

* Find the instance's public IP address:

```
$ aws ec2 describe-instances --query 'Reservations[*].Instances[*].[InstanceId, PublicIpAddress, State.Name]' --o text
i-0cfe5ea7ed066a99a     None    terminated
i-08488b8f265efb192     3.72.47.246     running
```

* Ssh to the instance:

```
$ INSTANCE_IP=3.72.47.246
$ ssh -oStrictHostKeyChecking=accept-new -i aws-key-pair.pem ec2-user@$INSTANCE_IP
```

* Sudo to root and look for error output from your `user_data` script:

```
$ sudo su -
# less /var/log/cloud-init-output.log
```

* And take a look at your `user_data` script as extracted by `cloud-init`:

```
# less /var/lib/cloud/instance/scripts/part-001
```

Hopefully, the failure reason will be obvious from `cloud-init-output.log`. Once resolved, don't forget to `poweroff` the instance.

Development
-----------

If adding new features, it's probably easiest to first establish a more permissive policy document during development and then tighten things back up afterward. For more on updating policies, see [here](docs/role-permissions.md).

E.g. the following enables all permissions for all resources for S3, CloudWatch Logs and DynamoDB:

```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "S3Actions",
            "Effect": "Allow",
            "Action": "s3:*",
            "Resource": "*"
        },
        {
            "Sid": "LogActions",
            "Effect": "Allow",
            "Action": "logs:*",
            "Resource": "*"
        },
        {
            "Sid": "DynamoDbActions",
            "Effect": "Allow",
            "Action": "dynamodb:*",
            "Resource": "*"
        }
    ]
}
```

Notes
-----

The [`user_data`](templates/user_data) script installs the v2 version of the AWS CLI. At the moment (mid 2022), Amazon Linux 2 still comes with just v1 installed. Once v2 is installed, you don't have to take any extra steps - it's installed in `/usr/local/bin` while v1 is installed in `/usr/bin` and `local` comes first in the default path so, it always takes precedence.

For other notes, see also:

* [`boto3-notes.md`](docs/boto3-notes.md).
* [`public-ip-address.md`](docs/public-ip-address.md)