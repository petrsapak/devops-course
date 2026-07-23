# Chapter 14 — Test

15 questions. Passing: 12/15.

---

**Q1.** "Agentless" — what does it mean for Ansible concretely, and what are the
two things a target host must have?

**Q2.** Push vs pull configuration management: which is Ansible, and name one
advantage of each model.

**Q3.** Terraform vs Ansible: state the division of labor, give one task in each
tool's lane, and describe the concrete handoff between them.

**Q4.** What does `ansible all -m ping` actually test (it's not ICMP)?

**Q5.** In run output, what do `ok`, `changed`, and `failed` mean — and what
should a second consecutive run of a correct playbook show?

**Q6.** Why is `ansible.builtin.apt: name=nginx state=present` idempotent while
`shell: apt-get install -y nginx` is not (in reporting terms), and what two task
keywords tame shell tasks?

**Q7.** What are handlers, when do they run, and what's the canonical use case?

**Q8.** Ten template tasks all `notify: Reload nginx`. Seven report `changed`.
How many reloads happen and when?

**Q9.** What are facts, how do you use one in a template, and what does
`--check --diff` give you?

**Q10.** Group `web` sets `http_port=8080`; host `web1` sets `http_port=9090`.
Which wins for web1 and what's the general rule?

**Q11.** What problem does ansible-vault solve, what does the file look like in
Git, and where must the vault password never live?

**Q12.** Name four standard directories of a role and what goes in each.

**Q13.** What do `serial: 1` and `max_fail_percentage: 0` accomplish together,
and which deployment-strategy concept from ch 10 does this implement?

**Q14.** Your ch 08 Jenkins needs 5 identical build agents (VMs with docker,
JDK, specific tools). Sketch the toolchain: what creates them, what configures
them, where does the config live?

**Q15.** Critique this task and rewrite it properly:
```yaml
- name: setup app config
  shell: echo "port=8080" > /etc/app/app.conf && systemctl restart app
```

---

<details>
<summary><b>Answer key</b></summary>

1. No agent software installed on targets; Ansible connects over SSH and
   executes modules remotely. Targets need: SSH access (key auth) and Python.
2. Ansible = push (control node reaches out on demand). Push: full control of
   *when*, natural for orchestrated campaigns; nothing to install. Pull
   (Chef/Puppet agents): scales to huge fleets and self-heals on schedule
   without a central runner reaching every node.
3. Terraform provisions infrastructure into existence; Ansible configures the
   inside of what exists. TF lane: create a VM/network/DNS record. Ansible
   lane: install packages, place config files, manage services/users. The
   handoff is Terraform outputs rendered into an inventory (for example with
   `local_file` + `templatefile`), followed by
   `ansible-playbook -i inventory.ini site.yml`.
4. SSH connectivity + authentication + a usable Python on the target (module
   round-trip) — i.e., "can Ansible manage this host", not "does it answer ICMP".
5. `ok`: state already correct, nothing done. `changed`: action taken to reach
   the declared state. `failed`: couldn't. Second run: all `ok`, `changed=0` —
   the idempotency proof.
6. The module checks current state first and reports honestly (`ok` when
   already installed); shell runs unconditionally and always reports `changed`
   (and re-executes side effects). Guards: `creates:`/`removes:` and
   `changed_when:` (plus `failed_when:`).
7. Tasks that run only when notified by a task that reported `changed`,
   executed once at the end of the play. Canonical: reload/restart a service
   only when its configuration actually changed.
8. One reload, at the end of the play — notifications deduplicate.
9. Facts: per-host system data gathered at play start (OS, IPs, CPUs, memory),
   available as variables — e.g. `{{ ansible_facts['default_ipv4']['address'] }}`
   in a Jinja2 template. `--check --diff`: dry run showing what *would* change
   and the file diffs — Ansible's `terraform plan`.
10. 9090 — host vars beat group vars; the most specific scope wins.
11. Committing secrets to Git in usable-but-safe form: AES256-encrypted YAML
    that diffs as ciphertext. The vault password itself: never in the repo —
    password manager, CI secret store, or `--vault-password-file` outside VCS.
12. `tasks/` (the work), `handlers/` (notified actions), `templates/` (Jinja2
    files), `defaults/` (overridable default vars), also `vars/` (fixed
    internals), `files/` (static files), `meta/` (dependencies). (Any four.)
13. One host at a time, abort the whole run on the first host failure —
    a rolling update with a blast radius of one. Ch 10: rolling deployment
    (with fail-fast instead of blind continuation).
14. Terraform creates the 5 VMs (and networking), outputs/generates the
    inventory; an Ansible playbook/role installs docker, JDK, agent tooling and
    registers them with Jenkins. Both the TF config and the playbook live in
    Git, run from CI, reviewed by PR.
15. Problems: shell instead of modules (always `changed`, restart storms every
    run), no idempotency, unconditional restart, no mode/ownership, clobbers the
    whole file. Proper:
    ```yaml
    - name: Deploy app config
      ansible.builtin.template:
        src: app.conf.j2        # contains port={{ app_port }}
        dest: /etc/app/app.conf
        mode: "0644"
      notify: Restart app

    handlers:
      - name: Restart app
        ansible.builtin.service:
          name: app
          state: restarted
    ```

</details>

**Scoring:** 12+ → [Chapter 15](../15-monitoring-observability/lesson.md). Below →
redo exercises 14.2, 14.3, 14.7 — idempotency, handlers, and serial rollouts are
the essence.
