#!/usr/bin/python3

import argparse
import os
import subprocess
import sys
import time

# helper function to print log messages depending on verbosity
def log (level, *msg):
    if args.verbose >= level:
        print(' '.join([str(x) for x in msg]), flush=True)

sys.dont_write_bytecode = True

# helper function to run and log processes
def runprog (name, progargs, env=None, exit_on_failure=True):
    log(1, 'Running', name)
    proc = subprocess.run(
        progargs,
        timeout = 300,
        capture_output = True,
        text = True,
        env = env,
    )
    if proc.returncode != 0:
        log(0,"#"*72)
        log(0,'Running', name, 'failed!')
        log(0,"Returncode:", proc.returncode)
        log(1,"#### STDOUT ####")
        log(1, proc.stdout)
        log(1, "#### STDERR ####")
        log(1, proc.stderr)
        log(0,"#"*72)
        if exit_on_failure:
            sys.exit(proc.returncode)
    return proc

def locale_debug(name):
    if args.verbose >= 2:
        log(2, name)
        log(2, 'output of /usr/bin/locale:')
        subprocess.run(['/usr/bin/locale'])
        prog = runprog('cat /etc/default/locale', ['cat', '/etc/default/locale'])
        log(2, prog.stdout, prog.stderr)
        # grep will exit 1 when it doesn't return anything, so don't fail on it.
        prog = runprog(
            'grep -v -P \'^#|^$\' /etc/locale.gen',
            ['grep', '-v', '-P', '^#|^$', '/etc/locale.gen'],
            exit_on_failure=False,
        )
        log(2, prog.stdout, prog.stderr)

parser = argparse.ArgumentParser(
    prog='ansible-test-integration.py',
    description='python script to run ansible-test integration against the Debian source package',
)

# Whether to run the default tests not in any other list
parser.add_argument(
    '--default-tests',
    action=argparse.BooleanOptionalAction,
    default=False,
    help='Run the default tests not listed anywhere else. (default: no)',
)

parser.add_argument(
    '--requires-root',
    action=argparse.BooleanOptionalAction,
    default=False,
    help='Run tests that require root. (default: no)',
)

parser.add_argument(
    '--requires-ssh',
    action=argparse.BooleanOptionalAction,
    default=False,
    help='Run tests that require a specially configured SSH server. (default: no)'
)

parser.add_argument(
    '--requires-apt-mark-manual',
    action=argparse.BooleanOptionalAction,
    default=False,
    help='Run tests that do "apt-mark manual" on certain packages. (default: no)',
)

parser.add_argument(
    '--fails-on-pip',
    action=argparse.BooleanOptionalAction,
    default=False,
    help='Run tests that run "pip3 install" on certain modules. (default: no)',
)

parser.add_argument(
    '--failing',
    action=argparse.BooleanOptionalAction,
    default=False,
    help='Run tests that fail on other reasons. (default: no)',
)

parser.add_argument(
    '--setup',
    action=argparse.BooleanOptionalAction,
    default=True,
    help='Setup testbed via sudo. (default: yes)',
)

parser.add_argument(
    '--dry-run',
    action=argparse.BooleanOptionalAction,
    default=False,
    help='Print the list of targets without actually running them',
)

parser.add_argument(
    '--check-test-lists',
    action=argparse.BooleanOptionalAction,
    default=False,
    help='Check if all the hardcoded integration tests from the other \
          flags (e.g. --requires-root, --failing, ,etc.) still exist \
          in the ansible-core test suite. Defaults to no. When set, \
          skips everything else.',
)
parser.add_argument(
    '--verbose', '-v',
    action='count',
    default=1,
    help='verbosity between 0 and 5. 0 will only emit errors. 1=INFO. \
          More for increasing levels of debug info. Defaults to 1.',
)

args = parser.parse_args()

# Don't set up test env when checking test lists
if args.check_test_lists:
    args.setup = False

locale_debug('locale before setting os.environ:')
os.environ['LANG'] = 'en_US.UTF-8'
locale_debug('locale after setting os.environ:')

if args.setup is True and args.dry_run == False:
    proc = runprog('testbed-setup.sh', ['sudo', './debian/tests/testbed-setup.sh'])
    log(0,"#### STDOUT ####")
    log(0, proc.stdout)
    log(0, "#### STDERR ####")
    log(0, proc.stderr)
    locale_debug('locale after running testbed-setup.sh:')

# integration tests requiring a running ssh server
integration_requires_ssh = {
    'become_unprivileged',
    'cli',
    'connection_paramiko_ssh',
    'connection_ssh',
    'delegate_to',
    'fetch',
    'module_tracebacks',
    'ssh_agent',
}

# integration tests requiring root because the apt module is used to
# install missing packages, or to mark packages as manually installed
integration_requires_apt_mark_manual = {
    #'ansible-galaxy-collection-scm',   # apt-mark manual git
    'ansible-pull',                    # apt-mark manual git
    #'debconf',                         # apt-mark manual debconf-utils
    'iptables',                        # apt-mark manual iptables
    'git',                             # apt-mark manual git
}

integration_fails_on_pip = {
    'ansible-galaxy-collection-cli',   # fails on pip
    'ansible-inventory',               # pip error: externally-managed-environment ## upstream fix
    'builtin_vars_prompt',             # passlib: pip error: externally-managed-environment
    'debugger',                        # pip installs pexpect
    'pause',                           # pip installs pexpect
}

integration_failing = {
    'ansible-galaxy-role':            'dict object has no attribute lnk_source',  ## needs upstream fix?
    'ansible-test-docker':            "pwsh doesn't exist in Debian yet",
    'ansible-test':                   'installs and runs python libs from remote',
    'ansible-test-debugging':         'requires running built binary instead of package binary',
    'ansible-test-installed':         'checks only valid if source tree has bin/ directory',
    'ansible-test-sanity':            'checks are only valid for the source tree',
    'ansible-test-units-forked':      '?????',
    'ansible-test-vendoring':         'Should test with ./bin/ansible-test which was removed in v2.18.0', ## needs upstream fix
    'deb822_repository':              'setup_deb_repo seems to generate a repo with hashsum mismatch',
    'facts_d':                        'seems to read an unreadable problem without error', ## needs upstream fix
    'infra':                          'requires hacking/test-module.py not present',
    'mount_facts':                    'makes assumptions about static/dynamic mounts without assuring they exist',
    'packaging_cli-doc':              'checks only valid if source tree has bin/ directory',
    'unarchive':                      'two unarchive tasks in a row, second one reports changed',
}

if subprocess.check_output(['dpkg', '--print-architecture'], text=True).rstrip('\n') not in {'amd64', 'ppc64el'}:
    integration_failing['binary_modules_posix'] = 'needs statically-built helloworld_linux_* from ci-files.testing.ansible.com'

# work around autopkgtest providing the source tree owned by a different user
if args.setup:
    runprog('git config hack for normal user', ['git', 'config', '--global', '--add', 'safe.directory', '*'])
    runprog('git config hack for root', ['sudo', 'git', 'config', '--global', '--add', 'safe.directory', '*'])

pyver = str(sys.version_info.major) + '.' + str(sys.version_info.minor)

overall_test_rc = 0
failed_tests = []
succeeded_tests = []

# retrieve a list of all integration tests
all_targets_cmd = runprog(
    'ansible-test to retrieve list of targets',
    ['ansible-test', 'integration', '--list-targets', '--allow-root', '--allow-destructive'],
    env={**os.environ, 'PYTHONPATH': os.path.join(os.getcwd(), 'test', 'lib')},
)

# Compile list of all targets
all_targets = set(all_targets_cmd.stdout.splitlines())

default_targets = list(
    all_targets
    - integration_requires_ssh
    - integration_requires_apt_mark_manual
    - integration_fails_on_pip
    - set(integration_failing.keys())
)

def check_if_list_in_all_targets( l1, name):
    l = l1 - all_targets
    global overall_test_rc # hack to change it out of func
    if len(l) !=0:
        log(0, name, 'has elements not in all_targets list!')
        for i in l:
            log(0, ' ', i)
        overall_test_rc = 1
        log(0, '  ^^^^ consider removing those.')
    else:
        log(0, name, 'looks good.')

if args.check_test_lists:
    check_if_list_in_all_targets(integration_requires_ssh, 'integration_requires_ssh')
    check_if_list_in_all_targets(integration_requires_apt_mark_manual, 'integration_requires_apt_mark_manual')
    check_if_list_in_all_targets(integration_fails_on_pip, 'integration_fails_on_pip')
    check_if_list_in_all_targets(integration_failing.keys(), 'integration_failing')
    sys.exit(overall_test_rc)

# compile a list of targets to run, depending on CLI parameters
targets = []
skipped = []

if args.default_tests is True:
    targets.extend(default_targets)
else:
    skipped.extend(default_targets)

if args.requires_ssh is True:
    targets.extend(integration_requires_ssh)
else:
    skipped.extend(integration_requires_ssh)

if args.requires_apt_mark_manual is True:
    targets.extend(integration_requires_apt_mark_manual)
else:
    skipped.extend(integration_requires_apt_mark_manual)

if args.fails_on_pip is True:
    targets.extend(integration_fails_on_pip)
else:
    skipped.extend(integration_fails_on_pip)

if args.failing is True:
    targets.extend(integration_failing)
else:
    skipped.extend(integration_failing)

# TODO: remove any tests that we're skipping from the list
# e.g. "cli" is in requires-root and also requires-ssh

targets.sort()
skipped.sort()

for i in targets:

    if args.dry_run is True:
        log(1, 'Would run ansible-test in', i)
        succeeded_tests.append({
          'name': i,
          'time': 0
        })
        continue

    log(0, "\n" + "#"*72)
    log(0, "#### Running integration tests in", i)
    log(0, "#"*72)

    cmdlist = [
        'ansible-test',
        'integration',
        '--allow-root',
        '--allow-destructive',
        '--venv-system-site-packages',
        '--python-interpreter',
        '/usr/bin/python3',
        '--python',
        pyver,
        '--local',
        '--color', 'yes',
        i,
        # '-vvvv', # uncomment for more test output
    ]

    env={
        **os.environ,
        'PYTHONPATH': os.path.join(os.getcwd(), 'test', 'lib'),
    }

    # Check if test requires root privileges via aliases file
    needs_root = False
    with open(os.path.join('./test/integration/targets', i, 'aliases')) as f:
        for line in f.read().splitlines():
            if line == 'needs/root':
                needs_root = True

    if needs_root is True:
        cmdlist = ['sudo', '--preserve-env=PYTHONPATH'] + cmdlist

    # For debugging permission errors on writing results output
    if args.verbose >= 3:
        subprocess.run(['ls', '-ld', './test/'])
        subprocess.run(['ls', '-ld', './test/results/'])
        subprocess.run(['ls', '-ld', './test/results/.tmp/'])
        subprocess.run(['ls', '-ld', './test/results/.tmp/output_dir/'])

    # fix any permission errors due to some root tests not cleaning up correctly
    subprocess.run(['sudo', 'chown', '-R', str(os.getuid()) + ':' + str(os.getgid()), './test'])

    start = time.time()
    proc = subprocess.run(cmdlist, env=env)
    end = time.time()

    if proc.returncode != 0:
        failed_tests.append({
          'name': i,
          'time': int( end - start)
        })
        overall_test_rc = proc.returncode
    else:
        succeeded_tests.append({
          'name': i,
          'time': int( end - start)
        })

if overall_test_rc != 0:
    log(0, "#"*72)
    log(0, "#### failed tests are:")
    for i in failed_tests:
        log(0, "####", i['name'])
    log(0, "#"*72)

if (args.default_tests is False
  and (args.failing or args.fails_on_pip or args.requires_ssh)
  and len(succeeded_tests) > 0):
    log(0, "#"*72)
    log(0, "#### succeeded tests are:")
    for i in succeeded_tests:
        log(0, "####", i['name'])
    log(0, "Consider removing these ^^^ tests from the failing list!")
    log(0, "#"*72)

log(1, '### TEST SUMMARY ###')
log(1, 'succeeded tests:', len(succeeded_tests))
log(1, 'failed tests:', len(failed_tests))
log(1, 'skipped tests:', len(skipped))

log(2, '### succeeded test list:')
for i in succeeded_tests:
    log(2, '{:<30} (elapsed time: {:>3}s)'.format( i['name'], i['time'] ) )
log(2, '### failed test list:')
for i in failed_tests:
    log(2, '{:<30} (elapsed time: {:>3}s)'.format( i['name'], i['time'] ) )
log(2, '### skipped test list:')
for i in skipped:
    log(2, i)

sys.exit(overall_test_rc)
