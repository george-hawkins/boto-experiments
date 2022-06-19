EC2 Security Group
==================

EC2 instances need a [security group](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-security-groups.html) that controls what incoming and outgoing traffic is allowed.

TLDR;
-----

Find your default VPC:

```
$ aws ec2 describe-vpcs --filters 'Name=is-default,Values=true' --query 'Vpcs[0].VpcId' --output text
None
```

If it says `None` then create one:

```
$ aws ec2 create-default-vpc --query 'Vpc.VpcId' --output text
vpc-080daca15075a1dba
```

Once you've created a default VPC (or if you already had one), create a security group:

```
$ name=RenderJobWorkerSecurityGroup
$ now=$(date --iso-8601=seconds --utc)
$ aws ec2 create-security-group --group-name $name --description "$name created $now" 
{
    "GroupId": "sg-02625cc42d9379973"
}
```

It'll create this security group using your default VPC - if you `describe-security-groups` (see below), you'll see it as an attribute of the group.

That's it. The rest of this page just goes into more details about creating default VPCs and security groups.

Create default VPC
------------------

A security group needs a VPC. You have to create a default VPC for each region that you want to use.

If you've spun up an EC2 instance via the EC2 web dashboard then this will have already created a default VPC for your region.

You can check like so:

```
$ aws ec2 describe-vpcs
{
    "Vpcs": [
        {
            "CidrBlock": "172.31.0.0/16",
            "DhcpOptionsId": "dopt-03c215267c0b2c98f",
            "State": "available",
            "VpcId": "vpc-08d25d0400f9bc892",
            "OwnerId": "585598036396",
            "InstanceTenancy": "default",
            "CidrBlockAssociationSet": [
                {
                    "AssociationId": "vpc-cidr-assoc-06f6980c2a9b51b8e",
                    "CidrBlock": "172.31.0.0/16",
                    "CidrBlockState": {
                        "State": "associated"
                    }
                }
            ],
            "IsDefault": true
        }
    ]
}
```

The `IsDefault` bit is the important bit.

Try looking at another region:

```
$ aws --region eu-west-1 ec2 describe-vpcs
{
    "Vpcs": []
}
```

If you want to create a default VPC for a region for which you don't already have one:


```
$ aws --region eu-west-1 ec2 create-default-vpc
{
    "Vpc": {
        "CidrBlock": "172.31.0.0/16",
        "DhcpOptionsId": "dopt-010e1e5215d07262c",
        "State": "pending",
        "VpcId": "vpc-0148e53126513820a",
        "OwnerId": "585598036396",
        "InstanceTenancy": "default",
        "Ipv6CidrBlockAssociationSet": [],
        "CidrBlockAssociationSet": [
            {
                "AssociationId": "vpc-cidr-assoc-090550ed7d77902e9",
                "CidrBlock": "172.31.0.0/16",
                "CidrBlockState": {
                    "State": "associated"
                }
            }
        ],
        "IsDefault": true,
        "Tags": []
    }
}
```

In the process of creating the default VPC, it will also create a VPC [internet gateway](https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Internet_Gateway.html) and several VPC [subnets](https://docs.aws.amazon.com/vpc/latest/userguide/configure-subnets.html) (one for each availability zone within the region, e.g. `eu-west-1a`, `eu-west-1b` and `eu-west-1a` for the `eu-west-1` region).

If you try to delete the default VPC for a region, it'll probably fail like this:

```
$ aws --region eu-west-1 ec2 delete-vpc --vpc-id vpc-0148e53126513820a

An error occurred (DependencyViolation) when calling the DeleteVpc operation: The vpc 'vpc-0148e53126513820a' has dependencies and cannot be deleted.
```

This is because you first have to remove the gateway and the subnets - you can do this via the CLI but it's easier to use the VPC web dashboard and delete it there (where it'll handle also deleting the dependencies).

Create security group
---------------------

```
$ default_vpc=$(aws ec2 describe-vpcs --filters 'Name=is-default,Values=true' --query 'Vpcs[0].VpcId' --output text)
$ echo $default_vpc 
vpc-08d25d0400f9bc892
$ name=RenderJobWorkerSecurityGroup
$ now=$(date --iso-8601=seconds --utc)
$ aws ec2 create-security-group --group-name $name --description "$name created $now" 
{
    "GroupId": "sg-02625cc42d9379973"
}
$ aws ec2 describe-security-groups --group-names $name
{
    "SecurityGroups": [
        {
            "Description": "RenderJobWorkerSecurityGroup created 2022-06-11T19:25:32+00:00",
            "GroupName": "RenderJobWorkerSecurityGroup",
            "IpPermissions": [],
            "OwnerId": "585598036396",
            "GroupId": "sg-02625cc42d9379973",
            "IpPermissionsEgress": [
                {
                    "IpProtocol": "-1",
                    "IpRanges": [
                        {
                            "CidrIp": "0.0.0.0/0"
                        }
                    ],
                    "Ipv6Ranges": [],
                    "PrefixListIds": [],
                    "UserIdGroupPairs": []
                }
            ],
            "VpcId": "vpc-08d25d0400f9bc892"
        }
    ]
}
```

Oddly, the description is mandatory, so I just use the same convention as the EC2 dashboard uses when creating security groups for you (when you launch an instance).

This creates a security group that allows all outgoing traffic but _no_ incoming traffic. If you e.g. wanted to allow incoming ssh traffic from your IP, you have to add a rule:

```
$ my_ip=$(curl -s https://checkip.amazonaws.com)
$ aws ec2 authorize-security-group-ingress --group-name $name --protocol tcp --port 22 --cidr $my_ip/32
```

Adding rules is described in more detail [here](https://docs.aws.amazon.com/cli/latest/userguide/cli-services-ec2-sg.html#configuring-a-security-group).
