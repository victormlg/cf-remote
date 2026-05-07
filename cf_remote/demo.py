import os
import json
import hashlib
import secrets
import string
from posixpath import dirname, join

from cf_remote import log
from cf_remote.paths import cf_remote_dir
from cf_remote.utils import save_file, strip_user
from cf_remote.ssh import scp, ssh_sudo, ssh_cmd, auto_connect


@auto_connect
def agent_run(data, *, connection=None):
    host = data["ssh_host"]
    agent = data["agent"]
    print("Triggering an agent run on: '{}'".format(host))
    command = "{} -Kf update.cf".format(agent)
    ssh_func = ssh_cmd if data["os"] == "windows" else ssh_sudo
    output = ssh_func(connection, command)
    log.debug(output)
    command = "{} -K".format(agent)
    output = ssh_func(connection, command)
    log.debug(output)


def generate_password():
    """Generate credentials for the demo admin user.

    Returns (password, salt, sha) where sha is the hex SHA-256 of
    salt + password concatenated with no separator. The password is meant
    to be shown to the user; only the salt and sha are sent to the host.
    """
    password = "".join(secrets.choice(string.ascii_letters) for _ in range(14))
    salt = "".join(secrets.choice(string.ascii_letters) for _ in range(10))
    sha = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return password, salt, sha


@auto_connect
def disable_password_dialog(host, salt, sha, *, connection=None):
    print("Disabling password change on hub: '{}'".format(host))

    template_path = join(dirname(__file__), "demo.sql")
    with open(template_path, "r") as f:
        sql = f.read()
    sql = sql.replace("__CF_REMOTE_SHA__", sha).replace("__CF_REMOTE_SALT__", salt)

    safe_host = strip_user(host).replace("/", "_").replace(":", "_")
    rendered_path = os.path.join(cf_remote_dir(), "demo-{}.sql".format(safe_host))
    save_file(rendered_path, sql)
    try:
        scp(rendered_path, host, connection=connection)
        query = os.path.basename(rendered_path)
        try:
            ssh_sudo(
                connection,
                '/var/cfengine/bin/psql cfsettings -f "{}"'.format(query),
            )
        finally:
            ssh_cmd(connection, 'rm -f "{}"'.format(query))
    finally:
        try:
            os.remove(rendered_path)
        except OSError as e:
            log.warning("Could not remove local '{}': {}".format(rendered_path, e))


def def_json(call_collect=False):
    d = {
        "classes": {
            "mpf_augments_control_enabled": ["any"],
            "services_autorun": ["any"],
            "cfengine_mp_fr_dependencies_auto_install": ["any"],
        },
        "vars": {
            "acl": ["0.0.0.0/0", "::/0"],
            "default_data_select_host_monitoring_include": [".*"],
            "default_data_select_policy_hub_monitoring_include": [".*"],
            "control_executor_splaytime": "1",
            "control_executor_schedule": ["any"],
            "control_hub_hub_schedule": ["any"],
        },
    }

    if call_collect:
        d["classes"]["client_initiated_reporting_enabled"] = ["any"]
        d["vars"]["control_server_call_collect_interval"] = "1"
        d["vars"]["mpf_access_rules_collect_calls_admit_ips"] = ["0.0.0.0/0"]
        d["vars"]["control_hub_exclude_hosts"] = ["0.0.0.0/0"]

    return d


@auto_connect
def install_def_json(host, *, connection=None, call_collect=False):
    print("Transferring def.json to hub: '{}'".format(host))
    data = json.dumps(def_json(call_collect), indent=2)
    path = os.path.join(cf_remote_dir("json"), "def.json")
    save_file(path, data)
    scp(path, host, connection=connection)
    ssh_sudo(connection, "cp def.json /var/cfengine/masterfiles/def.json")
