Role permissions
================

What a role can do is determined by a policy document. Once you've created a policy, role and profile, you simply need to edit the policy document and set it as the new default version for the policy:

```
$ vim policies/experiments_policy.json
$ aws iam create-policy-version --set-as-default --policy-arn $POLICY_ARN --policy-document file://policies/experiments_policy.json
```

Policies are automatically versioned so, assuming you're not interested in switching back to older versions, just delete them:

```
$ OLD_IDS=$(aws iam list-policy-versions --policy-arn $POLICY_ARN | jq -r '.Versions | .[] | select(.IsDefaultVersion | not) | .VersionId')
$ for id in $OLD_IDS
do
    aws iam delete-policy-version --policy-arn $POLICY_ARN --version-id $id
done
```

Oddly, there's no `--filter` argument for `list-policy-versions`, hence the use of `jq` above.

If you don't delete old versions, you'll eventually hit this limit and have to delete them:

```
An error occurred (LimitExceeded) when calling the CreatePolicyVersion operation: A managed policy can have up to 5 versions. Before you create a new version, you must delete an existing version.
```

For more detail on the policy, role and profile, see the section below.

Determining permissions
-----------------------

To determine the permissions needed for an AWS CLI action, do:

```
$ aws --debug s3 cp s3://render-job-bucket-4a636430-6e3a-4056-bfda-7125bb4d3e47 . --recursive 2>&1 | sed -n 's/.*Event request.created.\([^:]*\).*/\1/p' | sort -u
s3.GetObject
s3.ListObjectsV2
```

```
aws --debug s3 cp s3://file-store-dcede0e0-aec4-4920-9532-c89a3a151af2/blender-3.2.0-linux-x64.tar.xz . 2>&1 | sed -n 's/.*Event request.created.\([^:]*\).*/\1/p' | sort -u
s3.GetObject
s3.HeadObject
```

Note: v1 of the AWS CLI sometimes uses more permissions for a particular operation than v2 - so watch out for differences between your locally installed version and the v1 version that is still the default in Amazon Linux 2 images.

So, above we see that the actions `s3.GetObject`, `s3.ListObjectsV2`, `s3.GetObject` and `s3.HeadObject` are required. If you look at the policy document, you'll see you need to specify actions - so it might seem obvious that you specify these values.

However, it seems that the `Actions` in the policy document are really permissions. In general there's a one-to-one mapping between the two - but it turns out that `ListObjectsV2` and `HeadObject` are not permissions.

You can check if an action name is also a permission name in the [actions reference](https://docs.aws.amazon.com/service-authorization/latest/reference/reference_policies_actions-resources-contextkeys.html). E.g. if you go to the [S3 section](https://docs.aws.amazon.com/service-authorization/latest/reference/reference_policies_actions-resources-contextkeys.html), you'll find `GetObject` is listed but `ListObjectsV2` and `HeadObject` are not.

That doesn't mean, you don't need a permission for `ListObjectsV2` or `HeadObject` - it just means things get more complicated. If you look up the [API reference](https://docs.aws.amazon.com/AmazonS3/latest/API/API_ListObjectsV2.html) for `ListObjectsV2` and search for "permission", you'll find you need the `ListBucket` permission. The same is true of `HeadObject`.

The term "permission" isn't used consistently and in most places the term "action" is used even when the two don't seem to be completely equivalent.

Note: nothing complains if you include names that aren't actually permissions, e.g. `HeadObject`, in the policy document.

This may all be a historical anomaly specific to S3 or it and some other older services - in the case of CloudWatch Logs and DynamoDB there weren't these discrepancies between action names and what needed to be specified in the policy document. Although, in the requests names (retrieved as above) the CloudWatch Log actions appeared as e.g. `cloudwatch-logs.CreateLogStream` but in the policy document one uses `logs` rather than `cloudwatch-logs`.

### Boto3

To determine which actions a Boto3 Python script uses, add the following to top of the scripts:

```
import logging
logging.basicConfig(filename="actions.log")
hooks_logger = logging.getLogger("botocore.hooks")
hooks_logger.setLevel(logging.DEBUG)
```

Then run the script and once it's completed and logged the relevant information to `actions.log`, the actions used can be extracted like so:

```
(venv) $ sed -n 's/.*Event request.created.\([^:]*\).*/\1/p' actions.log | sort -u
cloudwatch-logs.CreateLogStream
cloudwatch-logs.PutLogEvents
dynamodb.DeleteItem
dynamodb.Scan
dynamodb.UpdateItem
s3.PutObject
```

### Final policy

Once, you've iterated over what's needed and what's not, you'll end up with something like this:

```
$ cat policies/experiments_policy.json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "S3Actions",
            "Effect": "Allow",
            "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
            "Resource": "arn:aws:s3:::render-job-*"
        },
        {
            "Sid": "LogActions",
            "Effect": "Allow",
            "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
            "Resource": "arn:aws:logs:*:*:log-group:render-job-*"
        },
        {
            "Sid": "DynamoDbActions",
            "Effect": "Allow",
            "Action": ["dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:Scan"],
            "Resource": "arn:aws:dynamodb:*:*:table/render-job-*"
        }
    ]
}
```

The format of ARNs is described [here](https://docs.aws.amazon.com/general/latest/gr/aws-arns-and-namespaces.html). Most ARNs require an account ID (or a wildcard `*` in its place) but S3 ARNs do not as S3 bucket names are unique across accounts and regions.

Note: the resource specifications above are still quite loose - for a more paranoid setup these could be tightened up further.

### Replacing the old RenderJobWorkerPolicy

Store the relevant policy ARN as `POLICY_ARN`:

```
$ aws iam list-policies --scope Local --query 'Policies[].Arn'
[
    "arn:aws:iam::585598036396:policy/RenderJobWorkerPolicy",
    "arn:aws:iam::585598036396:policy/ExperimentsPolicy"
]
POLICY_ARN=arn:aws:iam::585598036396:policy/RenderJobWorkerPolicy
```

Update the old policy file with the one established through experimenting, create a new default policy version and delete old versions:

```
$ mv policies/experiments_policy.json policies/render_job_worker_policy.json
$ aws iam create-policy-version --set-as-default --policy-arn $POLICY_ARN --policy-document file://policies/render_job_worker_policy.json
{
    "PolicyVersion": {
        "VersionId": "v2",
        "IsDefaultVersion": true,
        "CreateDate": "2022-06-25T14:15:38+00:00"
    }
}
$ OLD_IDS=$(aws iam list-policy-versions --policy-arn $POLICY_ARN | jq -r '.Versions | .[] | select(.IsDefaultVersion | not) | .VersionId')
$ for id in $OLD_IDS
do
    aws iam delete-policy-version --policy-arn $POLICY_ARN --version-id $id
done
```

Above, you see `IsDefaultVersion` is true, as required, and that the new `VersionId` is `v2`. To confirm that this version is as expected:

```
$ aws iam get-policy-version --policy-arn $POLICY_ARN --version-id v2
{
    "PolicyVersion": {
        "Document": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "S3Actions",
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        ...
```

Policy, role and profile in detail
----------------------------------

Let's go through the whole process of creating an instance, creating a policy, role and profile for it and then updating the policy.

First launch an instance using the `launch-ec2-instance` script covered in the "launching instances" section [here](https://github.com/george-hawkins/aws-notes):

```
$ ./launch-ec2-instance t2.micro
Using Amazon Linux 2 Kernel 5.10 AMI 2.0.20220606.1 x86_64 HVM gp2 (amzn2-ami-kernel-5.10-hvm-2.0.20220606.1-x86_64-gp2)
Instance ID: i-0ba90fa3ac2496f36
To connect:
$ INSTANCE_IP=3.122.245.113
$ ssh -oStrictHostKeyChecking=accept-new -i aws-key-pair.pem ec2-user@$INSTANCE_IP
For Ubuntu servers, the user name is 'ubuntu' rather than 'ec2-user'.
```

Then connect using the instructions output by the script:

```
$ export INSTANCE_IP=3.122.245.113
$ ssh -oStrictHostKeyChecking=accept-new -i aws-key-pair.pem ec2-user@$INSTANCE_IP
```

Assuming, you're only running a single instance at the moment, find it like so:

```
INSTANCE_ID=$(aws ec2 describe-instances --filter 'Name=instance-state-name,Values=running' --query 'Reservations[].Instances[].InstanceId' --output text)
```

Or just set `INSTANCE_ID` from the "Instance ID" value shown in the output from `launch-ec2-instance` above:

```
$ INSTANCE_ID=i-0ba90fa3ac2496f36
```

Choose a base name for policy, role and profile:

```
$ IAM_BASE_NAME=Experiments
```

Create the policy that will be the basis of our experiments with permissions:

```
$ cat > policies/experiments_policy.json << 'EOF'
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "S3ListBucket",
            "Effect": "Allow",
            "Action": ["s3:*"],
            "Resource": "*"
        }
    ]
}
EOF
$ POLICY_ARN=$(aws iam create-policy --policy-name "${IAM_BASE_NAME}Policy" --policy-document file://policies/experiments_policy.json --query 'Policy.Arn' --output text)
```

Create the corresponding role and attach the policy to it:

```
$ aws iam create-role --role-name "${IAM_BASE_NAME}Role" --assume-role-policy-document file://policies/ec2-trust-policy.json
$ aws iam attach-role-policy --role-name "${IAM_BASE_NAME}Role" --policy-arn $POLICY_ARN
```

Finally, create a profile and attach the role to it:

```
$ aws iam create-instance-profile --instance-profile-name "${IAM_BASE_NAME}Profile"
$ aws iam add-role-to-instance-profile --role-name "${IAM_BASE_NAME}Role" --instance-profile-name "${IAM_BASE_NAME}Profile"
```

Once the role and profile are created, nothing further needs to be done with them - any changes to permissions are achieved simply by creating new default versions of the underlying policy.

To associate the profile with an existing EC2 instance first, disassociate any existing profile associations:

```
$ ASSOCIATION_ID=$(aws ec2 describe-iam-instance-profile-associations --filter "Name=instance-id,Values=$INSTANCE_ID" --query 'IamInstanceProfileAssociations[].AssociationId' --output text)
$ if [ "$ASSOCIATION_ID" != "" ]
then
    aws ec2 disassociate-iam-instance-profile --association-id $ASSOCIATION_ID
fi
```

And associate the new profile:

```
$ aws ec2 associate-iam-instance-profile --instance-id $INSTANCE_ID --iam-instance-profile "Name=${IAM_BASE_NAME}Profile"
```

Now, to iterate over different permission settings, just update the policy document and register it as the new default version of the policy:

```
$ vim policies/experiments_policy.json 
$ aws iam create-policy-version --set-as-default --policy-arn $POLICY_ARN --policy-document file://policies/experiments_policy.json
```

You can only store 5 versions of a policy so, rather than hit this limit at some arbitrary time, just delete old versions each time you add a new one:

```
$ OLD_IDS=$(aws iam list-policy-versions --policy-arn $POLICY_ARN | jq -r '.Versions | .[] | select(.IsDefaultVersion | not) | .VersionId')
$ for id in $OLD_IDS
do
    aws iam delete-policy-version --policy-arn $POLICY_ARN --version-id $id
done
```

It takes less than a minute for any change to become visible on any currently running EC2 instances.

To get the current policy version, first find the current default version:

```
$ aws iam get-policy-version --policy-arn $POLICY_ARN
{
    "Versions": [
        {
            "VersionId": "v6",
            "IsDefaultVersion": true,
            "CreateDate": "2022-06-25T12:05:44+00:00"
        }
    ]
}
```

Then query this version:

```
$ aws iam get-policy-version --policy-arn $POLICY_ARN --version-id v6
{
    "PolicyVersion": {
        "Document": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "S3Actions",
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:HeadObject",
                        "s3:ListObjectsV2"
                    ],
                    "Resource": "arn:aws:s3:::render-job-*"
                },
                ...
```