# Chapter 14 — Exercises

## Lab setup — a 3-node fleet in Docker

Install Ansible: `sudo apt install -y ansible ansible-lint` (WSL2).

Build a pretend server image and run three of them:

```bash
mkdir -p ~/devops/ch14/lab && cd ~/devops/ch14/lab
ssh-keygen -t ed25519 -f ~/.ssh/ansible_lab -N ""

cat > Dockerfile <<'EOF'
FROM ubuntu:24.04
RUN apt-get update && apt-get install -y openssh-server sudo python3 && \
    useradd -m -s /bin/bash ansible && \
    echo "ansible ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/ansible && \
    mkdir -p /home/ansible/.ssh /run/sshd
COPY ansible_lab.pub /home/ansible/.ssh/authorized_keys
RUN chown -R ansible:ansible /home/ansible/.ssh && chmod 700 /home/ansible/.ssh && chmod 600 /home/ansible/.ssh/authorized_keys
CMD ["/usr/sbin/sshd", "-D"]
EOF

cp ~/.ssh/ansible_lab.pub .
docker build -t labnode .
docker network create --subnet 172.28.0.0/24 ansiblelab
for i in 1 2 3; do
  docker run -d --name node$i --network ansiblelab --ip 172.28.0.1$i labnode
done
ssh -i ~/.ssh/ansible_lab ansible@172.28.0.11 hostname   # accept key, verify
```

(Note: containers-as-servers is a lab trick — no systemd, so we use nginx in
daemon-off mode or `service` module fallbacks; noted where it matters.)

---

## Exercise 14.1 — Inventory + ping

1. Write `inventory.ini`: node1+node2 in `[web]`, node3 in `[db]`, group vars
   setting `ansible_user=ansible` and the key file.
2. `ansible all -i inventory.ini -m ping` — three greens.
3. Ad-hoc recon: `uptime` on all, free memory on db only, and gather facts from
   node1 — find its `ansible_facts['default_ipv4']` and OS family.

**Verify:** ping returns `pong` from all three; you can explain why Ansible's
`ping` proves more than ICMP would (SSH auth + Python present).

## Exercise 14.2 — First playbook + idempotency proof

1. Write `base.yml` for `all`: install packages `[curl, jq, htop]` (loop),
   create file `/etc/motd` with content "Managed by Ansible" (copy module),
   create user `deploy` (user module).
2. Run it. Count the `changed` items.
3. **Run it again.** Count `changed` now.
4. `--check --diff` a third run.

**Verify:** second run: `changed=0`, all `ok` — idempotency demonstrated. Check
mode showed "nothing would change" without touching the hosts.

## Exercise 14.3 — Templates, handlers, and the reload-only-if-changed pattern

1. Playbook `web.yml` for group `web`: install nginx, template
   `site.conf.j2` → `/etc/nginx/sites-available/default` (vars: `http_port`
   from inventory, plus `{{ inventory_hostname }}` in a comment), handler
   "Restart nginx" (in the container lab: `shell: nginx -s reload || nginx`
   with `changed_when: true` — or the service module where it works).
2. Start nginx the lab way: task `shell: nginx` with `creates: /run/nginx.pid`
   (an idempotency guard on a shell task — deliberately, to learn the technique).
3. Run; curl both nodes from WSL (`curl 172.28.0.11:80`).
4. Run again with NO changes — did the handler fire?
5. Change `http_port` in inventory (e.g. 8080), rerun — now did it fire? Curl
   the new port.

**Verify:** handler fired only when the template task reported `changed` — you
implemented "reload only on config change" and used `creates:` to tame a shell task.

## Exercise 14.4 — Facts-driven config

Extend the template: render a header comment with the host's IP and CPU count
(`ansible_facts['processor_vcpus']`), and serve a per-host index.html
(template) showing hostname + group membership (`{{ group_names }}`).

**Verify:** curling node1 vs node2 shows different self-descriptions from ONE
template — config that adapts to its host.

## Exercise 14.5 — Vault

1. `ansible-vault create group_vars/db/vault.yml` with `vault_db_password: s3cretpw`.
2. Reference it from `group_vars/db/vars.yml` (`db_password: "{{ vault_db_password }}"`).
3. Playbook task (db group): template a `/etc/app/db.conf` containing the
   password. Run with `--ask-vault-pass`.
4. Inspect: `cat group_vars/db/vault.yml` (ciphertext — safe for Git) vs the
   rendered file on node3.
5. Try running WITHOUT the vault password — read the error.

**Verify:** secret encrypted at rest in the repo, plaintext only on the target;
you know the failure mode when the password is missing.

## Exercise 14.6 — Refactor into a role

1. `ansible-galaxy init roles/webserver` and move the web tasks/templates/
   handlers into it; `defaults/main.yml` holds `http_port: 80`.
2. `site.yml` becomes: hosts web → role webserver (override port via role vars
   for one experiment).
3. Run `ansible-lint` over the project and fix what it flags (naming, fqcn —
   `ansible.builtin.` prefixes, mode on files...).

**Verify:** same behavior as 14.3/14.4 with a `site.yml` under 10 lines, and a
clean (or consciously-waived) lint run.

## Exercise 14.7 — Rolling change with verification

The centerpiece: a config change rolled across the web fleet safely.

1. Playbook `rollout.yml`: hosts web, `serial: 1`, `max_fail_percentage: 0`.
   Tasks: deploy a new template version (bump a `config_version` var rendered
   into index.html) → reload → **verify** with `uri` module hitting the node's
   http endpoint expecting 200, `retries: 5`.
2. Run it and watch the order: node1 fully done (change+verify) before node2 starts.
3. Sabotage drill: break the template for the *next* run (e.g., make the verify
   expect a string that won't be there, or template an invalid config), run, and
   observe: node1 fails → **campaign aborts** → node2 untouched, still serving.
4. Fix and rerun.

**Verify:** the abort left the fleet 1-broken-2-healthy instead of 3-broken —
`serial` + verification is the difference between an incident and an annoyance.
Connect it: this is a rolling update (ch 10) hand-built; K8s did it with
readiness probes (ch 12).

## Exercise 14.8 — Terraform → Ansible handoff (integration)

1. In `~/devops/ch14/tf`, write a Terraform config (ch 13 skills) that creates
   the three lab containers (docker provider — image `labnode`, the static IPs)
   AND generates the inventory:
   `resource "local_file" "inventory" { content = templatefile("inventory.tftpl", {...}) ... }`.
2. `terraform apply`, then run your `site.yml` against the generated inventory.
3. `terraform destroy`, apply again, re-run Ansible — full environment from
   nothing in two commands.

**Verify:** you rebuilt and reconfigured the entire fleet with
`terraform apply && ansible-playbook -i inventory.ini site.yml` — provision →
configure, the classic pipeline, entirely from code in Git.

---

**Cleanup:** `docker rm -f node1 node2 node3 && docker network rm ansiblelab`
(or let 14.8's `terraform destroy` do it — the better habit).
