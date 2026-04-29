#!/usr/bin/sh

# helper script called from within ansible-test-integration.py to

set -eu

# workaround for various integration tests trying to do this and failing
# due to missing root permission
echo 'apt-mark changes'
/usr/bin/apt-mark manual debconf-utils || true
/usr/bin/apt-mark manual equivs || true
/usr/bin/apt-mark manual git || true
/usr/bin/apt-mark manual iptables || true
/usr/bin/apt-mark manual libfile-fcntllock-perl || true
/usr/bin/apt-mark manual openssl || true
/usr/bin/apt-mark manual python3-distlib || true

# Set default locale to en_US.UTF-8 to remove lots of warnings when
# running the tests
echo 'debconf selection changes'
# These values get overwritten by what is in the config files when
# running dpkg-reconfigure, see  https://bugs.debian.org/684134
cat << EOF | debconf-set-selections
locales	locales/default_environment_locale	select	en_US.UTF-8
locales	locales/locales_to_be_generated	multiselect	en_US.UTF-8 UTF-8
EOF

# So set these values manually in the config files.
cat > /etc/locale.gen << EOF
en_US.UTF-8 UTF-8
fr_FR.UTF-8 UTF-8 # used in unarchive integration test
EOF
echo 'LANG=en_US.UTF-8' > /etc/locale.conf
echo 'LANG=en_US.UTF-8' > /etc/default/locale

echo 'dpkg-reconfigure changes'
dpkg-reconfigure --frontend=noninteractive locales

# create empty authorized_keys for integration test 'copy'
[ -d /root/.ssh ] || mkdir /root/.ssh/

touch /root/.ssh/authorized_keys

# allow pip to install system packages for the tests
rm -f /usr/lib/python3*/EXTERNALLY-MANAGED

# Workaround for integration test "apt", because of policy in base-files
# See
# MODULE FAILURE: No start of json char found
# Traceback (most recent call last):
#   File \"<stdin>\", line 121, in <module>
#   File \"<stdin>\", line 113, in _ansiballz_main
#   File \"<stdin>\", line 61, in invoke_module
#   File \"<frozen runpy>\", line 226, in run_module
#   File \"<frozen runpy>\", line 98, in _run_module_code
#   File \"<frozen runpy>\", line 88, in _run_code
#   File \"/tmp/ansible_apt_repository_payload_88mfa8n7/ansible_apt_repository_payload.zip/ansible/modules/apt_repository.py\", line 195, in <module>
#   File \"/usr/lib/python3/dist-packages/aptsources/distro.py\", line 547, in get_distro
#     release = os_release[\"VERSION_ID\"]
#               ~~~~~~~~~~^^^^^^^^^^^^^^
# KeyError: 'VERSION_ID'
#
# Fixed in sid: https://bugs.debian.org/1088402
# Still leaving this here because ansible assumes that it's set pretty
# much everywhere.
grep VERSION_ID /etc/os-release || echo 'VERSION_ID="99"' >> /etc/os-release
