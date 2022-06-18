Public IP address
-----------------

**Question:** can I create an instance without any public IP at all?

**Answer:** not without difficulty as they need a public IP to access the internet. The alternative is:

* To set up some form of VPN (that does have a public IP) that can mediate between your instance and the public internet.
* Work out how to avoid interaction with the public internet and only interact with AWS resources.

In my case avoiding public internet would mean getting `pip` to use locally available packages.

### Installing PyPi packages without internet

See:

* https://stackoverflow.com/questions/11091623/how-to-install-packages-offline
* https://pip.pypa.io/en/stable/user_guide/#installing-from-local-packages
* https://thilinamad.medium.com/install-python-packages-via-pip-without-an-internet-connection-b3dee83b4c2d

