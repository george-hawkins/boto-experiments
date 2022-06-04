

```
$ python3 -m venv venv
$ source venv/bin/activate
(venv) $ pip install --upgrade pip
```

Install boto3 and the [boto3-stubs](https://pypi.org/project/boto3-stubs/) type annotations:

```
(venv) $ pip install boto3
(venv) $ pip install 'boto3-stubs[essential,logs]'
```

Note: the stubs won't pull in `boto3` as a dependency - you have to install both `boto3` and the stubs.

Metadata
--------

On an EC2 instance, you can get your region like so:

```
$ curl http://instance-data/latest/meta-data/placement/availability-zone/
```

For all the other metadata, you can retrieve, see:

```
$ curl http://instance-data/latest/meta-data
```

On non-Amazon AMIs, you may have to use `169.254.169.254` rather than `instance-data` as the host.

You can also use the command xxx:

```
$ ec2-metadata
ami-id: ami-09439f09c55136ecf
...
$ ec2-metadata --help
...
```

You should also be able to do:

```
$ cloud-init query --all
```

However, Amazon use an old version of `cloud-init` that will only work if run as root.

But you can find the JSON data it would query in `/run/cloud-init/instance-data.json`

S3 access on an EC2 instance
----------------------------

If you try and `ls` one of your buckets, it'll fail:

```
$ aws s3 ls s3://d9983d65-b1bd-4bcd-a442-aae6c9b0d607
Unable to locate credentials. You can configure credentials by running "aws configure".
```

But rather than uploading your credentials (which you should be keeping extra safe), you can:

<https://www.youtube.com/watch?v=0zq9eC1M5Dk>

Similarly, try:

```
$ mkdir boto3-experiments
$ cd boto3-experiments
$ python3 -m venv venv
$ source venv/bin/activate
$ pip install --upgrade pip
$ pip install boto3
$ cat > main.py << 'EOF'
import boto3

# Something that access S3.

EOF
$ python main.py
None
```

This will also fail.

So, in the AWS web console, go to _IAM / Roles_. Click the _Create Role_ button, select _EC2_ under _Common use cases_ and click _Next_.

Click _Create Policy_, in the end it does seem easier to use the _JSON_ tab rather than the _Visual Editor_ tab. But let's give it a try.

![img.png](visual-editor.png)

First, choose a service, i.e. S3. Then in _Actions_, expand _List_ and tick _ListBucket_.

The _Manual actions_ section is a bit confusing initially, click _add actions_ and enter:

![img.png](wildcard-action.png)

This is a quick alternative to going through the _Read_, _Write_ etc. sections and ticking all the actions ending with "Object" - these are the ones you need if you want to read, write and delete objects.

Then got to the _Resources_ section and tick _All resources_ to stop it complaining that you have to specify ARNs for some of the actions you selected.

Now, jump to the _JSON_ tab and you'll see this translates to just:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "s3:*Object",
                "s3:ListBucket"
            ],
            "Resource": "*"
        }
    ]
}
```

`"Sid"` is the statement ID - you could put whatever you want there (it just has to uniquely identify the given statement within the list of 1 or more statements).

Note: the above isn't far off from the already available _AmazonS3FullAccess_ policy.

You could split things out and specify specific resources:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "ListObjectsInBucket",
            "Effect": "Allow",
            "Action": ["s3:ListBucket"],
            "Resource": ["arn:aws:s3:::bucket-name"]
        },
        {
            "Sid": "AllObjectActions",
            "Effect": "Allow",
            "Action": "s3:*Object",
            "Resource": ["arn:aws:s3:::bucket-name/*"]
        }
    ]
}
```

Note the wildcard in the second `"Resource"` value. This example is from [here](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_examples_s3_rw-bucket.html) in the AWS IAM documentation.

OK - now we have the policy details, click _Next_, skip over _Tags_ and on the _Review_ page just enter a name like "S3ReadWriteAccessPolicy".

Now, return to the _Roles_ browser tab (you we're in the _Add permissions_ section) where you were before pressing _Create Policy_.

In the _Permission policies_ section, tick the policy that you just created and click _Next_.

Just enter a _Role Name_, like "S3ReadWriteAccessRole", and click _Create Role_.

---

Now, back to the _EC2 / Instances_ console. Oddly, after all the roles stuff, the region confusingly defaults to something other than my eu-central-1 zone and no instances are shown.

Once you've switched region if necessary, tick your instance, go to _Actions / Security / Modify IAM role_, select the newly created role and click _Update IAM role_.


Get the region locally or on EC2
--------------------------------

```
import boto3

session = boto3.session.Session()
current_region = session.region_name

if current_region is None:
    from botocore.utils import IMDSRegionProvider
    import botocore.session

    imds_region_provider = IMDSRegionProvider(session=botocore.session.get_session())
    current_region=imds_region_provider.provide()

print(current_region)
```

All `session.region_name` does is get the `region` value from `~/.aws/config`.

On an EC2 instance with no `~/.aws/config`, it'll return `None`.

In that situation, `IMDSRegionProvider` will do the equivalent of `curl http://instance-data/latest/meta-data/placement/availability-zone/`.

Write to an existing bucket from on EC2
---------------------------------------

For an instance that's got the necessary IAM role (as described above):

```
import boto3
from botocore.config import Config

# As of Boto3 1.23.8, the default `defaults_mode` is still `legacy`.
# See https://docs.aws.amazon.com/sdkref/latest/guide/feature-smart-config-defaults.html
config = Config(defaults_mode="standard")
s3_resource = boto3.resource("s3", config=config)

# This is a bucket I created previously.
bucket = s3_resource.Bucket(name="97e1721f-caf9-4729-9aa2-e62ab5c3991c")

obj = bucket.Object("my_first_file")

obj.put(Body="foo bar")

print("Success")
```

Get latest version of AMI
-------------------------

    $ aws ec2 describe-images --owners aws-marketplace --filter 'Name=name,Values=amzn2-ami-graphics-hvm-*' --query 'sort_by(Images, &CreationDate)[-1].Name' --output text