Creating a GPU AMI
==================

Start an instance (here a `g5.xlarge` instance) running the latest minimal Amazon Linux 2 AMI and get its instance ID:

```
$ aws ec2 run-instances --image-id resolve:ssm:/aws/service/ami-amazon-linux-latest/al2022-ami-minimal-kernel-default-x86_64 --instance-type g5.xlarge --key-name AwsKeyPair --security-group-ids BasicSecurityGroup --query 'Instances[].InstanceId' --output text
i-0bfa26b553bc82dec
$ INSTANCE_ID=i-0bfa26b553bc82dec
```

Note: see the _Starting an instance_ section and the _Security group creation_ section [here](https://github.com/george-hawkins/aws-notes) for how to create a key pair and a suitable security group.

Find its public IP and ssh to it:

```
$ aws ec2 describe-instances --instance-id $INSTANCE_ID --query 'Reservations[*].Instances[*].[InstanceId, PublicIpAddress, State.Name]' --output text
i-0bfa26b553bc82dec     54.93.249.54    running
$ INSTANCE_IP=54.93.249.54
$ ssh -oStrictHostKeyChecking=accept-new -i aws-key-pair.pem ec2-user@$INSTANCE_IP
Warning: Permanently added '54.93.249.54' (ECDSA) to the list of known hosts.

A newer release of "Amazon Linux" is available.
  Version 2022.0.20230118:
Run "/usr/bin/dnf check-release-update" for full release and version update info
   ,     #_
   ~\_  ####_        Amazon Linux 2022
  ~~  \_#####\       Preview
  ~~     \###|
  ~~       \#/ ___   https://aws.amazon.com/linux/amazon-linux-2022
   ~~       V~' '->
    ~~~         /
      ~~._.   _/
         _/ _/
       _/m/'
```

And switch to root:

```
$ sudo su -
```

**Important:** when you copy and paste into the ssh session, for whatever reason, the pasted text sometimes remains highlighted after you press enter and you actually have to press enter twice for anything to really happen.

Note that above, it tells us that `A newer release of "Amazon Linux" is available.` even tho' we asked for the latest one. Even if you search all image IDs, you won't find this newer version. You need to upgrade to the specified version like so:

```
# dnf upgrade --releasever=2022.0.20230118 -y
# rm -f /etc/motd
```

If the `motd` isn't removed, it'll continue complaining at logon that a newer release is available despite having upgraded.

Make sure the `yum` caches are up-to-date and upgrade everything that needs to upgraded (and remove outdated packages):

```
# yum clean expire-cache
# yum check-update
# yum upgrade -y
```

Install basic Blender dependencies needed for Cycles:

```
# yum install -y libGL libXrender libXi
```

At this point Blender would be able to run Cycles using CPU rendering:

```
$ blender -b input.blend -E CYCLES -o //result/ -f 1
```

Find the latest production branch driver version (locally or else you'll have to install `jq` on the EC2 instance):

```
$ curl -s https://docs.nvidia.com/datacenter/tesla/drivers/releases.json | jq --raw-output '[.[] | select(.type == "production branch") | .driver_info[0].release_version][0]'
525.60.13
```

The `jq` is looking for the latest driver version where the `type` is `production branch` in the JSON retrieved from <https://docs.nvidia.com/datacenter/tesla/drivers/releases.json>.

Nvidia publishes various different pages, release notes and forms that supposedly show or retrieve the latest suitable driver version but are out of sync with each other. The `releases.json` file _seems_ to be definitive.

Note: oddly Nvidia doesn't provide a package manager installable version of its drivers for Amazon Linux 2 so, you have to get the `.run` version that actually builds the driver and then installs it.

Then retrieve this version:

```
# BASE_URL=https://us.download.nvidia.com/tesla
# DRIVER_VERSION=525.60.13
# curl -O $BASE_URL/$DRIVER_VERSION/NVIDIA-Linux-x86_64-$DRIVER_VERSION.run
```

Install the dependencies needed to by the `.run` script:

```
# yum install -y kernel-devel vulkan-loader libglvnd-devel automake bzip2
```

And install the driver:

```
# sh NVIDIA-Linux-x86_64-$DRIVER_VERSION.run
```

This uses an ncurses UI, you can also run it with `--ui=none` for just a simple command line prompting interface but it's slightly less clear.

The installer complains that it `was forced to guess the X library path` and suggests you install `pkg-config` but it's already installed and the real issue is that it calls `pkg-config` for `xorg-server`. We can see that `pkg-config` can lookup various variables for `x11` but none for `xorg-server`:

```
$ pkg-config --print-variables x11
xthreadlib
includedir
libdir
exec_prefix
prefix
pcfiledir
$ pkg-config --variable=libdir x11   
/usr/lib64
$ pkg-config --print-provides xorg-server
```

This isn't an issue and the installer's guess is fine.

When asked whether to `Install NVIDIA's 32-bit compatibility libraries`, just select `No`.

You can now safely uninstall the various things needed to build the Nvidia kernel modules etc. and the driver download:

```
$ yum remove -y kernel-devel vulkan-loader libglvnd-devel automake bzip2
# rm -f NVIDIA-Linux-x86_64-$DRIVER_VERSION.run
```

Now, you can create an AMI from this instance. First, clear out logs and exit (but don't shut down) the instance:

```
# journalctl --rotate
# journalctl --vacuum-time=1s
# exit
$ exit
```

And create an image (with a name that must be unique within the region) using the `INSTANCE_ID` value we captured earlier:

```
$ UUID=$(< /proc/sys/kernel/random/uuid)
$ IMAGE_NAME="boto3-renderer-$UUID"
$ aws ec2 create-image --instance-id $INSTANCE_ID --name $IMAGE_NAME --output text
ami-0181deac890894a6f
$ IMAGE_ID=ami-0181deac890894a6f
```

**Important:** do not terminate the original instance until the `create-image` completes its work. To check its progress:

```
$ aws ec2 describe-images --image-id $IMAGE_ID --query 'Images[*].[State, StateReason.Message]' --output text
pending None
```

This can take around 5 minutes. Once the state shows `available` you can terminate the original instance:

```
$ aws ec2 terminate-instances --instance-ids $INSTANCE_ID
```

Now, launch an instance using the image ID value output by `create-image` above:

```
$ aws ec2 run-instances --image-id $IMAGE_ID --instance-type g5.xlarge --key-name AwsKeyPair --security-group-ids BasicSecurityGroup --query 'Instances[].InstanceId' --output text
i-01085d57944b10009 
$ INSTANCE_ID=i-01085d57944b10009 
```

And then connect to it:

```
$ aws ec2 describe-instances --instance-id $INSTANCE_ID --query 'Reservations[*].Instances[*].[InstanceId, PublicIpAddress, State.Name]' --output text
i-01085d57944b10009     3.73.83.109     running
$ INSTANCE_IP=3.73.83.109
$ ssh -oStrictHostKeyChecking=accept-new -i aws-key-pair.pem ec2-user@$INSTANCE_IP
```

If you go to the AWS EC2 dashboard and go to the _AMIs_ section, you can check for stale images that you've created and delete them. 

**Important:** select the AMI and then select _Deregister AMI_, note the snapshot associated with this AMI and then go to the _Snapshots_ section and select this snapshot and select _Delete snapshot_.

Search for image ID
-------------------

To find an image ID using a wildcard name like `boto3-renderer-*`, do:

```
$ aws ec2 describe-images --owner self --filters "Name=name,Values=boto3-renderer-*" --query 'Images[*].ImageId' --output text
ami-0181deac890894a6f
```

Note the use of `--owner self`, this restricts the search to your own AMIs - you don't want to pick up similarly named AMIs created by other people.

Checking Cycles and Optix
-------------------------

You can check that Blender works with Cycles and Optix as follows.

On your local machine, create a `.blend` file with a minimal scene with Cycles set as the renderer with just 32 samples and copy the file to the EC2 instance:

```
$ INSTANCE_IP=3.72.246.75
$ scp -i aws-key-pair.pem input.blend ec2-user@$INSTANCE_IP:
```

Then ssh to the instance and...

```
$ version=3.3.3
$ url=$(curl -s -D- -L https://www.blender.org/download/release/Blender${version%.*}/blender-$version-linux-x64.tar.xz -o /dev/null | sed -n 's/^refresh:.*url=\(.*\.xz\).*/\1/p')
$ curl -sL $url -o blender.tar.xz
$ mkdir blender
$ time tar -xf blender.tar.xz --strip-components=1 -C blender
```

And now you can render the `.blend` file:

```
$ ./blender/blender -b input.blend -E CYCLES -o //result/ -f 1 -- --cycles-device OPTIX
```

And you can copy the resulting PNG to your local machine and view it:

```
$ scp -i aws-key-pair.pem ec2-user@$INSTANCE_IP:result/0001.png .
$ eog 0001.png
```
