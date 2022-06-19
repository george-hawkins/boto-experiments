IAM Role
========

EC2 instances need a [role and profile](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles.html) in order to interact with other AWS resources such as S3 buckets.

TLDR;
-----

Create a policy (with the policy document [`render_job_worker_policy.json`](../policies/render_job_worker_policy.json)) and note the returned ARN:

```
$ aws iam create-policy --policy-name RenderJobWorkerPolicy --policy-document file://policies/render_job_worker_policy.json --query 'Policy.Arn' --output text
arn:aws:iam::585598036396:policy/RenderJobWorkerPolicy
```

Create a role (with the trust policy [`ec2-trust-policy.json`](../policies/ec2-trust-policy.json)) and attach the use the ARN of the just created policy to attach it to the role:

```
$ aws iam create-role --role-name RenderJobWorkerRole --assume-role-policy-document file://policies/ec2-trust-policy.json
$ aws iam attach-role-policy --role-name RenderJobWorkerRole --policy-arn arn:aws:iam::585598036396:policy/RenderJobWorkerPolicy
```

Note: while both are called policy documents, they describe different things - `ec2-trust-policy.json` describes who's involved and `render_job_worker_policy.json` describes what they can do.

Finally, create a profile and add the role to it:

```
$ aws iam create-instance-profile --instance-profile-name RenderJobWorkerProfile
$ aws iam add-role-to-instance-profile --role-name RenderJobWorkerRole --instance-profile-name RenderJobWorkerProfile
```

This profile can now be associated with EC2 instances.

That's it. The rest of this page just goes into more detail about creating polies, roles and profiles; and covers associating a profile with a running EC2 instance.

Create policy
-------------

First we create a policy document:

```
$ mkdir policies
$ cat > policies/render_job_worker_policy.json << 'EOF'
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "S3ListBucket",
            "Effect": "Allow",
            "Action": ["s3:ListBucket"],
            "Resource": "*"
        },
        {
            "Sid": "S3AllObjectActions",
            "Effect": "Allow",
            "Action": "s3:*Object",
            "Resource": "*"
        }
    ]
}
EOF
```

And create a policy from this JSON file:

```
$ aws iam create-policy --policy-name RenderJobWorkerPolicy1 --policy-document file://policies/render_job_worker_policy.json --query 'Policy.Arn' --output text
arn:aws:iam::585598036396:policy/RenderJobWorkerPolicy1
```

Create role and profile
-----------------------

If you create a role via the web dashboard, the first thing you're asked to do is to select the trusted entity involved. In this case, we want the trusted entity to be the AWS service EC2. And on the final step of creating the role (via the dashboard), you'd see a piece of JSON specifying the trusted entity. Here we create an identical piece of JSON as our first step:

```
$ cat > policies/ec2-trust-policy.json << 'EOF'
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "sts:AssumeRole"
            ],
            "Principal": {
                "Service": [
                    "ec2.amazonaws.com"
                ]
            }
        }
    ]
}
EOF
```

Then we create a blank role for the entity specified by the JSON:

    $ aws iam create-role --role-name RenderJobWorkerRole1 --assume-role-policy-document file://policies/ec2-trust-policy.json

Then we add the policy created up above to the role (there's no option to specify the policy using its name rather than its ARN):

    $ aws iam attach-role-policy --role-name RenderJobWorkerRole1 --policy-arn arn:aws:iam::585598036396:policy/RenderJobWorkerPolicy1

Then finally, we need to create a profile and associate the role with the profile:

```
$ aws iam create-instance-profile --instance-profile-name RenderJobWorkerProfile1
$ aws iam add-role-to-instance-profile --role-name RenderJobWorkerRole1 --instance-profile-name RenderJobWorkerProfile1
```

Note: if you create roles via the dashboard then you never see profiles - a profile is silently created under-the-covers with the same name as the profile. And you're always given the impression that it's roles that are associated with EC2 instances but under-the-covers, it's really the identically named profile that's associated with instances.

Associating a profile with a running EC2 instance
-------------------------------------------------

First, see if there are any associations that you might want to remove first:

```
$ aws ec2 describe-iam-instance-profile-associations

    "IamInstanceProfileAssociations": [
        {
            "AssociationId": "iip-assoc-036708c748f6c7a2e",
            ...
$ aws ec2 disassociate-iam-instance-profile --association-id iip-assoc-036708c748f6c7a2e
```

Now, associate the just created profile with a particular instance:

```
$ aws ec2 associate-iam-instance-profile --instance-id i-08dabea9f68b1f328 --iam-instance-profile Name=RenderJobWorkerProfile1
$ aws ec2 describe-iam-instance-profile-associations
```
