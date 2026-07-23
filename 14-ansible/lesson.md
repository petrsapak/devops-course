# Chapter 14 — Configuration Management: Ansible

## Learning objectives

1. Place Ansible correctly: configuration management vs provisioning, push vs pull, agentless.
2. Write inventories (static + groups + variables) and ad-hoc commands.
3. Write playbooks with idempotent modules, handlers, templates, and vault-encrypted secrets.
4. Structure reusable roles.
5. Know when Ansible is the right tool in a container-era stack — and when it isn't.

Lab model: Ansible needs machines to configure. We'll use **Docker containers
running sshd as pretend servers** — a standard trick giving you a 3-node fleet
on your laptop.

---

## 1. What Ansible is

Terraform creates the server; **Ansible makes the server correct**: packages
installed, config files placed, services running, users present. Its defining
traits:

- **Agentless**: connects over plain SSH (ch 02 skills) — nothing to install on
  targets except Python. Enormous practical advantage for adoption and for
  managing appliances/legacy boxes.
- **Push model**: you (or CI) run `ansible-playbook`, it reaches out to N hosts
  in parallel. (Contrast: Chef/Puppet agents *pull* from a server on schedule.)
- **Idempotent modules**: you declare state (`package X present`, `line Y in
  file Z`, `service running`), the module checks before acting. Re-running a
  playbook on a converged host = all green "ok", zero changes — ch 01's
  idempotency, industrialized.
- **YAML playbooks** — readable by sysadmins, reviewable in PRs.

Where it shines today, honestly: configuring VM fleets and bare metal; the
"pet" servers that legitimately remain (build agents — your ch 08 Jenkins nodes!,
databases, network gear, on-prem anything); one-off orchestrated operations
(rolling restarts, patching campaigns); bootstrapping hosts to the point where
containers take over. Where it's fading: app deployment on Kubernetes (GitOps
won that — ch 12).

## 2. Inventory — who to manage

`inventory.ini`:

```ini
[web]
web1 ansible_host=172.20.0.11
web2 ansible_host=172.20.0.12

[db]
db1 ansible_host=172.20.0.13

[production:children]     # group of groups
web
db

[web:vars]                 # group variables
http_port=8080

[all:vars]
ansible_user=ansible
ansible_ssh_private_key_file=~/.ssh/ansible_lab
```

- Hosts belong to **groups**; plays target groups. `all` is built in.
- Variables attach at host, group, or global level (precedence: host beats
  group beats all — most specific wins).
- Real setups often use **dynamic inventory** (a plugin queries the cloud API /
  Docker and the inventory is always live — no stale lists).

Test connectivity (the ritual first step):

```bash
ansible all -i inventory.ini -m ping        # not ICMP! SSH + Python check
```

> **Tool:** `ansible` — the *ad-hoc* command: run one module against a host pattern, right now. (Playbooks, next section, are the durable form; the CLI grammar is the same.)
> **The pieces:** `all` — which hosts, by group name or pattern (`web`, `web1`, `all`) · `-i inventory.ini` — which **i**nventory file describes those hosts · `-m ping` — which **m**odule to run. Despite the name, the ping module doesn't send ICMP: it SSHes in, checks Python works, and reports — i.e., it validates the *entire Ansible control path*.
> **Expect:**
> ```
> web1 | SUCCESS => { "changed": false, "ping": "pong" }
> web2 | UNREACHABLE! => { "msg": "Failed to connect to the host via ssh: ..." }
> ```
> Green `SUCCESS` per host = ready for real work. `UNREACHABLE` is an SSH problem (key, user, IP — debug with ch 02's ssh directly), not an Ansible problem.

### Ad-hoc commands — parallel SSH with modules

```bash
ansible web -i inventory.ini -m command -a "uptime"
ansible all -i inventory.ini -m setup | less        # "facts": OS, IPs, memory...
ansible db -i inventory.ini -m apt -a "name=htop state=present" --become
```

> **New flags:** `-a` — **a**rguments for the module: free text for `command` (the literal command line to run), `key=value` pairs for real modules (`name=htop state=present` = "the package htop should exist") · `--become` — escalate to root on the target (sudo) — required for package installs, service management, writing to `/etc` · `-m setup` — the fact-gathering module; its giant JSON of OS/network/hardware details is what playbook conditionals (`when: ansible_facts[...]`) later key off.

`--become` = sudo. Ad-hoc is for inspection and emergencies; anything done twice
belongs in a playbook.

## 3. Playbooks

The chapter's reference example — configure nginx web servers:

```yaml
# site.yml
- name: Configure web servers
  hosts: web
  become: true                    # sudo for the whole play

  vars:
    server_name: lab.example.com

  tasks:
    - name: Install nginx
      ansible.builtin.apt:
        name: nginx
        state: present
        update_cache: true

    - name: Deploy site config
      ansible.builtin.template:
        src: templates/site.conf.j2
        dest: /etc/nginx/sites-available/default
        mode: "0644"
      notify: Reload nginx        # ← handler trigger

    - name: Ensure nginx is running and enabled
      ansible.builtin.service:
        name: nginx
        state: started
        enabled: true

  handlers:
    - name: Reload nginx
      ansible.builtin.service:
        name: nginx
        state: reloaded
```

```bash
ansible-playbook -i inventory.ini site.yml
ansible-playbook -i inventory.ini site.yml --check --diff   # DRY RUN + show diffs
ansible-playbook -i inventory.ini site.yml --limit web1     # subset
```

> **Tool:** `ansible-playbook` — executes a playbook: for each play, gather facts from the targeted hosts, then run every task against them (in parallel across hosts, sequential within a host).
> **Flags:** `--check` — dry run: modules report what they *would* change without changing it; `--diff` adds unified diffs of file/template changes. Together they are Ansible's `terraform plan`, and belong in CI on every PR · `--limit web1` — restrict this run to a subset of the play's hosts (one canary machine first, then the fleet — pairs with `serial`, §6).
> **Expect:**
> ```
> TASK [Install nginx] *******************************************
> ok: [web2]
> changed: [web1]
>
> RUNNING HANDLER [Reload nginx] *********************************
> changed: [web1]
>
> PLAY RECAP *****************************************************
> web1 : ok=3  changed=2  unreachable=0  failed=0
> web2 : ok=3  changed=0  unreachable=0  failed=0
> ```
> Read the recap like a ledger: `changed=2` on web1 (it acted), `changed=0` on web2 (already correct — idempotency visible). Note the handler ran only on web1 — the only host whose config actually changed. **A second run should show `changed=0` everywhere; if a task reports `changed` every run, it's written non-idempotently (usually a naked `shell` task) — fix it.**

### The concepts inside

**Modules, not commands.** `apt`, `template`, `service`, `copy`, `file`,
`lineinfile`, `user`, `git`, `docker_container`… each encapsulates idempotent
"ensure state" logic. `command`/`shell` are the escape hatches — they run every
time (not idempotent) unless you add `creates:`/`changed_when:` guards. A
playbook full of `shell` is a bash script wearing a costume — use modules.

**Run output** is a per-host, per-task ledger: `ok` (already correct),
`changed` (acted), `failed`. Second run of a correct playbook: all `ok` — that's
the idempotency proof, and `--check` mode (dry run) is the plan-before-apply
habit from ch 13 in Ansible clothing.

**Handlers** run once at the end of the play, only if notified by a `changed`
task — the canonical "reload the service only if its config actually changed"
pattern. Ten config tasks can notify one handler; one reload happens.

**Templates (Jinja2)** — files with variables and logic:

```jinja
# templates/site.conf.j2
server {
    listen {{ http_port }};
    server_name {{ server_name }};
    # Generated by Ansible for {{ inventory_hostname }} — manual edits will be overwritten
    location / {
        root /var/www/html;
    }
}
```

`{{ var }}`, `{% for %}`, `{% if %}` — per-host config files from one source.
**Facts** (gathered at play start) are variables too: `{{ ansible_facts['os_family'] }}`,
`{{ ansible_facts['default_ipv4']['address'] }}` — configs that adapt to the host.

**Loops and conditionals:**

```yaml
    - name: Install base packages
      ansible.builtin.apt:
        name: "{{ item }}"
        state: present
      loop: [curl, jq, htop, unzip]

    - name: Debian-only task
      ansible.builtin.apt: ...
      when: ansible_facts['os_family'] == "Debian"
```

## 4. Secrets: ansible-vault

Encrypted variable files that can live in Git:

```bash
ansible-vault create group_vars/db/vault.yml     # opens editor; content encrypted at rest
ansible-vault edit group_vars/db/vault.yml
ansible-playbook site.yml --ask-vault-pass       # or --vault-password-file
```

> **Tool:** `ansible-vault` — symmetric encryption for YAML files, built into Ansible. `create`/`edit` open your `$EDITOR` with plaintext and encrypt on save (`view` for read-only; `encrypt`/`decrypt` convert existing files). On disk you see only `$ANSIBLE_VAULT;1.1;AES256` + hex — safe to commit.
> **At run time:** `--ask-vault-pass` prompts interactively; `--vault-password-file ~/.vault_pass` reads the password from a (0600-permission, gitignored) file — the non-interactive form CI uses, with the password injected from the CI secret store (ch 07).

Inside — normal YAML (`db_password: s3cret`); on disk — AES256 ciphertext.
Pattern: keep a plaintext `vars.yml` referencing `{{ vault_db_password }}` from
the encrypted file, so greppability survives. The vault password itself comes
from a password manager or CI secret (ch 07) — never from a sticky note.

## 5. Roles — the reuse unit

Playbooks grow; **roles** are the modular packaging (Jenkins shared libraries /
Helm charts / TF modules — same instinct, fourth spelling):

```
roles/nginx_site/
├── tasks/main.yml        # the tasks
├── handlers/main.yml
├── templates/site.conf.j2
├── defaults/main.yml     # overridable defaults (lowest precedence)
└── vars/main.yml         # fixed internals (high precedence)
```

```yaml
# site.yml shrinks to composition:
- hosts: web
  become: true
  roles:
    - role: nginx_site
      vars:
        server_name: lab.example.com
```

`ansible-galaxy init roles/nginx_site` scaffolds the layout. **Ansible Galaxy**
(galaxy.ansible.com) hosts community roles (install postgres, harden ssh…) —
audit before trusting, like any dependency.

Project shape that scales:

```
ansible/
├── inventory/production.ini  (+ staging.ini)
├── group_vars/{all,web,db}/vars.yml + vault.yml
├── roles/...
└── site.yml (+ playbooks/patch.yml, deploy.yml...)
```

## 6. Operational patterns worth stealing

**Rolling operations** — `serial` turns a play into a rolling wave (ch 10's
strategy, for config):

```yaml
- hosts: web
  serial: 1                    # one host at a time (or "25%")
  max_fail_percentage: 0       # abort the campaign on first failure
  tasks: [ ... patch, reboot, verify ... ]
```

**Verify after change** — don't assume, check (the ch 02 healthcheck instinct):

```yaml
    - name: Wait for service to answer
      ansible.builtin.uri:
        url: "http://{{ ansible_host }}:{{ http_port }}/health"
        status_code: 200
      retries: 10
      delay: 3
      register: health
      until: health is succeeded
```

**Ansible in CI** — same shape as everything since ch 07: PR runs
`ansible-lint` + `--check --diff` (the plan); merge runs the playbook (the
apply); secrets via vault + CI-injected vault password.

**Terraform + Ansible together** — the classic handoff: Terraform creates the
machines, Ansible makes them correct. The minimal mechanical link is Terraform
*generating the inventory file* as just one more resource:

```hcl
# alongside the ch 13 for_each fleet (exercise 13.5):
resource "local_file" "inventory" {
  filename = "${path.module}/inventory.ini"
  content  = <<-EOT
    [web]
    %{~ for c in docker_container.web ~}
    ${c.name} ansible_host=${c.network_data[0].ip_address}
    %{~ endfor ~}

    [all:vars]
    ansible_user=ansible
    ansible_ssh_private_key_file=~/.ssh/ansible_lab
  EOT
}
```

```bash
terraform apply -auto-approve && ansible-playbook -i inventory.ini site.yml
```

> **How the handoff works:** `local_file` is a resource like any other — created/updated on apply, so the inventory always reflects the machines Terraform just made. The `%{ for }` template loop writes one host line per container, pulling each *real* IP from provider attributes; nothing is typed by hand, so nothing goes stale. The `&&` (ch 02) chains the tools: provision, then configure, one command.
> **At scale** the generated file gives way to **dynamic inventory** (§2) — the `aws_ec2`/`azure_rm` inventory plugins query the cloud API live at playbook start, so there is no file to go stale at all. Either way the division of labor is identical: Terraform owns *existence*, Ansible owns *contents*.

## Further reading

- docs.ansible.com — "Get started", module index (bookmark it), Vault docs.
- Jeff Geerling, *Ansible for DevOps* — the practical classic (+ his galaxy roles as examples).

## Abbreviations

| Abbreviation | Stands for | In a nutshell |
|---|---|---|
| SSH | Secure Shell | The encrypted transport Ansible uses to reach every managed host |
| YAML | YAML Ain't Markup Language | The format playbooks and inventories are written in |
| AES256 | Advanced Encryption Standard, 256-bit key | The cipher `ansible-vault` uses to encrypt secret files at rest |

**Next:** [Exercises](exercises.md) → [Test](test.md) → [Chapter 15: Monitoring & Observability](../15-monitoring-observability/lesson.md)
