"""
db_init.py  --  CommandVault database initializer
Run this once (or to reset to defaults):

    python db_init.py

It creates vault.db in the same directory with:
  - Full schema (FTS5 index + triggers)
  - Starter library: Cisco, Linux, Proxmox, Ansible
"""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vault.db")


SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS commands (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  category    TEXT    NOT NULL,
  subcategory TEXT,
  title       TEXT    NOT NULL,
  command     TEXT    NOT NULL,
  description TEXT,
  tags        TEXT,
  is_favorite INTEGER NOT NULL DEFAULT 0,
  created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_cmd_category ON commands(category);
CREATE INDEX IF NOT EXISTS idx_cmd_title    ON commands(title);

CREATE VIRTUAL TABLE IF NOT EXISTS commands_fts USING fts5(
  title, command, description, tags, category, subcategory,
  content='commands', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS commands_ai AFTER INSERT ON commands BEGIN
  INSERT INTO commands_fts(rowid, title, command, description, tags, category, subcategory)
  VALUES (new.id, new.title, new.command, new.description, new.tags, new.category, new.subcategory);
END;

CREATE TRIGGER IF NOT EXISTS commands_ad AFTER DELETE ON commands BEGIN
  INSERT INTO commands_fts(commands_fts, rowid, title, command, description, tags, category, subcategory)
  VALUES ('delete', old.id, old.title, old.command, old.description, old.tags, old.category, old.subcategory);
END;

CREATE TRIGGER IF NOT EXISTS commands_au AFTER UPDATE ON commands BEGIN
  INSERT INTO commands_fts(commands_fts, rowid, title, command, description, tags, category, subcategory)
  VALUES ('delete', old.id, old.title, old.command, old.description, old.tags, old.category, old.subcategory);
  INSERT INTO commands_fts(rowid, title, command, description, tags, category, subcategory)
  VALUES (new.id, new.title, new.command, new.description, new.tags, new.category, new.subcategory);
END;
"""

# (category, subcategory, title, command, description, tags, is_favorite)
SEED_DATA = [
    # ---- Cisco / VLAN --------------------------------------------------------
    ("Cisco", "VLAN", "Show VLAN brief", "show vlan brief",
     "List all VLANs with port assignments", "vlan,l2,ccna", 1),
    ("Cisco", "VLAN", "Show VLAN detail", "show vlan id {vlan_id}",
     "Detail for a specific VLAN ID", "vlan,l2", 0),
    ("Cisco", "VLAN", "Create VLAN", "vlan {vlan_id}\n name {vlan_name}",
     "Create VLAN and assign name", "vlan,config", 0),
    ("Cisco", "VLAN", "Delete VLAN", "no vlan {vlan_id}",
     "Remove a VLAN from VTP database", "vlan,config", 0),
    ("Cisco", "VLAN", "Show interfaces trunk", "show interfaces trunk",
     "Show all trunk ports and allowed VLANs", "vlan,trunk,l2", 1),
    ("Cisco", "VLAN", "Show VLAN on interface", "show interfaces {iface} trunk",
     "Trunk info for a specific interface", "vlan,trunk", 0),
    ("Cisco", "VLAN", "Set interface access VLAN", "interface {iface}\n switchport mode access\n switchport access vlan {vlan_id}",
     "Assign interface to VLAN in access mode", "vlan,config,l2", 0),
    ("Cisco", "VLAN", "Add VLAN to trunk", "interface {iface}\n switchport trunk allowed vlan add {vlan_id}",
     "Allow additional VLAN on trunk port", "vlan,trunk,config", 0),

    # ---- Cisco / MAC ---------------------------------------------------------
    ("Cisco", "MAC", "Show MAC address table", "show mac address-table",
     "Full MAC address table", "mac,l2,ccna", 1),
    ("Cisco", "MAC", "Show MAC on interface", "show mac address-table interface {iface}",
     "MACs learned on a specific port", "mac,l2", 0),
    ("Cisco", "MAC", "Show MAC for VLAN", "show mac address-table vlan {vlan_id}",
     "MACs in a specific VLAN", "mac,vlan,l2", 0),
    ("Cisco", "MAC", "Show MAC dynamic count", "show mac address-table count",
     "Count of dynamic MAC entries", "mac,l2", 0),
    ("Cisco", "MAC", "Clear MAC table", "clear mac address-table dynamic",
     "Flush all dynamic MAC entries", "mac,l2,clear", 0),

    # ---- Cisco / ARP ---------------------------------------------------------
    ("Cisco", "ARP", "Show ARP table", "show ip arp",
     "Full ARP table", "arp,l3,ccna", 1),
    ("Cisco", "ARP", "Show ARP for interface", "show ip arp {iface}",
     "ARP entries on specific interface", "arp,l3", 0),
    ("Cisco", "ARP", "Show ARP for IP", "show ip arp {ip}",
     "ARP entry for a specific IP", "arp,l3", 0),
    ("Cisco", "ARP", "Clear ARP cache", "clear arp-cache",
     "Flush ARP table", "arp,l3,clear", 0),

    # ---- Cisco / Interfaces --------------------------------------------------
    ("Cisco", "Interfaces", "Show interfaces", "show interfaces",
     "All interface statistics", "interface,l1,ccna", 1),
    ("Cisco", "Interfaces", "Show interface status", "show interfaces status",
     "Port status summary (speed, duplex, VLAN)", "interface,l1,ccna", 1),
    ("Cisco", "Interfaces", "Show interface description", "show interfaces description",
     "Interface descriptions and state", "interface,l1", 0),
    ("Cisco", "Interfaces", "Show specific interface", "show interfaces {iface}",
     "Full detail for one interface", "interface,l1", 0),
    ("Cisco", "Interfaces", "Show interface counters", "show interfaces {iface} counters",
     "Traffic counters for an interface", "interface,l1,counters", 0),
    ("Cisco", "Interfaces", "Show CDP neighbors", "show cdp neighbors detail",
     "Neighbors with IP, platform, interface", "cdp,topology,ccna", 1),
    ("Cisco", "Interfaces", "Shutdown interface", "interface {iface}\n shutdown",
     "Administratively disable a port", "interface,config", 0),
    ("Cisco", "Interfaces", "No shutdown interface", "interface {iface}\n no shutdown",
     "Bring up a disabled port", "interface,config", 0),

    # ---- Cisco / Routing -----------------------------------------------------
    ("Cisco", "Routing", "Show IP route", "show ip route",
     "Full routing table", "routing,l3,ccna", 1),
    ("Cisco", "Routing", "Show IP route summary", "show ip route summary",
     "Route count per protocol", "routing,l3", 0),
    ("Cisco", "Routing", "Show IP route for prefix", "show ip route {prefix}",
     "Route lookup for a specific prefix", "routing,l3", 0),
    ("Cisco", "Routing", "Add static route", "ip route {prefix} {mask} {next_hop}",
     "Configure a static route", "routing,config", 0),
    ("Cisco", "Routing", "Show OSPF neighbors", "show ip ospf neighbor",
     "OSPF adjacency table", "ospf,routing,l3", 0),
    ("Cisco", "Routing", "Show OSPF database", "show ip ospf database",
     "OSPF LSDB summary", "ospf,routing", 0),
    ("Cisco", "Routing", "Show BGP summary", "show ip bgp summary",
     "BGP neighbor table", "bgp,routing,l3", 0),

    # ---- Cisco / STP ---------------------------------------------------------
    ("Cisco", "STP", "Show spanning-tree", "show spanning-tree",
     "STP state for all VLANs", "stp,l2,ccna", 1),
    ("Cisco", "STP", "Show STP for VLAN", "show spanning-tree vlan {vlan_id}",
     "STP topology for a specific VLAN", "stp,l2,vlan", 0),
    ("Cisco", "STP", "Show STP root", "show spanning-tree root",
     "Root bridge per VLAN", "stp,l2", 0),
    ("Cisco", "STP", "Show STP blocklist", "show spanning-tree blockedports",
     "Ports in BLK state", "stp,l2", 0),
    ("Cisco", "STP", "Set STP root primary", "spanning-tree vlan {vlan_id} root primary",
     "Force this switch as root for VLAN", "stp,config", 0),

    # ---- Cisco / Port-Channel ------------------------------------------------
    ("Cisco", "Port-Channel", "Show etherchannel summary", "show etherchannel summary",
     "Port-Channel status (LACP/PAgP)", "portchannel,lacp,l2", 1),
    ("Cisco", "Port-Channel", "Show etherchannel detail", "show etherchannel {pc_num} detail",
     "Detailed Port-Channel info", "portchannel,lacp", 0),
    ("Cisco", "Port-Channel", "Create LACP Port-Channel", "interface range {iface_range}\n channel-group {pc_num} mode active",
     "Bundle interfaces in LACP active mode", "portchannel,lacp,config", 0),

    # ---- Cisco / ACL ---------------------------------------------------------
    ("Cisco", "ACL", "Show access-lists", "show access-lists",
     "All configured ACLs with hit counts", "acl,security", 1),
    ("Cisco", "ACL", "Show specific ACL", "show access-lists {acl_name}",
     "Specific ACL entries and counters", "acl,security", 0),
    ("Cisco", "ACL", "Show interface ACL", "show ip interface {iface}",
     "ACL applied to an interface", "acl,interface,security", 0),

    # ---- Cisco / NAT ---------------------------------------------------------
    ("Cisco", "NAT", "Show NAT translations", "show ip nat translations",
     "Active NAT sessions", "nat,l3", 1),
    ("Cisco", "NAT", "Show NAT statistics", "show ip nat statistics",
     "NAT hit/miss counters", "nat,l3", 0),
    ("Cisco", "NAT", "Clear NAT translations", "clear ip nat translation *",
     "Flush all dynamic NAT entries", "nat,clear", 0),

    # ---- Cisco / System ------------------------------------------------------
    ("Cisco", "System", "Show version", "show version",
     "IOS version, uptime, flash, RAM", "system,ccna", 1),
    ("Cisco", "System", "Show running-config", "show running-config",
     "Current active configuration", "config,system", 1),
    ("Cisco", "System", "Show startup-config", "show startup-config",
     "Saved configuration in NVRAM", "config,system", 0),
    ("Cisco", "System", "Copy run to startup", "copy running-config startup-config",
     "Save configuration", "config,save,ccna", 1),
    ("Cisco", "System", "Show flash", "show flash:",
     "Flash filesystem contents", "system,flash", 0),
    ("Cisco", "System", "Show CPU", "show processes cpu sorted",
     "CPU utilization per process", "system,performance", 0),
    ("Cisco", "System", "Show memory", "show processes memory sorted",
     "Memory usage per process", "system,performance", 0),
    ("Cisco", "System", "Show log", "show logging",
     "System log buffer", "system,logs,ccna", 1),
    ("Cisco", "System", "Show NTP status", "show ntp status",
     "NTP synchronization state", "system,ntp,time", 0),
    ("Cisco", "System", "Ping", "ping {target}",
     "ICMP ping to a host", "ping,connectivity", 1),
    ("Cisco", "System", "Traceroute", "traceroute {target}",
     "Trace hops to a destination", "trace,connectivity", 0),
    ("Cisco", "System", "Reload", "reload",
     "Restart the device", "system,reload", 0),

    # ---- Linux / Disk --------------------------------------------------------
    ("Linux", "Disk", "Disk usage (human)", "df -h",
     "Filesystem usage in human-readable format", "disk,storage", 1),
    ("Linux", "Disk", "Disk usage inode", "df -i",
     "Inode usage per filesystem", "disk,inode", 0),
    ("Linux", "Disk", "Directory size", "du -sh {path}",
     "Size of a directory", "disk,storage", 0),
    ("Linux", "Disk", "Top 10 largest dirs", "du -h --max-depth=1 {path} | sort -rh | head -10",
     "Find largest subdirectories", "disk,storage,find", 0),
    ("Linux", "Disk", "List block devices", "lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE",
     "Block device tree with filesystem info", "disk,block", 0),
    ("Linux", "Disk", "Disk I/O stats", "iostat -xz 1 5",
     "I/O utilization per device", "disk,performance,io", 0),

    # ---- Linux / Network -----------------------------------------------------
    ("Linux", "Network", "Show IP addresses", "ip a",
     "All network interfaces and IPs", "network,ip,linux", 1),
    ("Linux", "Network", "Show routing table", "ip route show",
     "Kernel routing table", "network,routing,linux", 1),
    ("Linux", "Network", "Show connections", "ss -tulnp",
     "Listening sockets with PID", "network,sockets,linux", 1),
    ("Linux", "Network", "Ping host", "ping -c 4 {host}",
     "ICMP test, 4 packets", "network,ping", 0),
    ("Linux", "Network", "Traceroute", "traceroute {host}",
     "Trace network path to host", "network,trace", 0),
    ("Linux", "Network", "DNS lookup", "dig {domain}",
     "DNS query for a domain", "network,dns", 0),
    ("Linux", "Network", "Reverse DNS", "dig -x {ip}",
     "PTR record for an IP", "network,dns", 0),
    ("Linux", "Network", "Curl HTTP status", "curl -o /dev/null -s -w '%{http_code}' {url}",
     "Get HTTP status code of a URL", "network,http,curl", 0),
    ("Linux", "Network", "Network interface stats", "ip -s link show {iface}",
     "TX/RX counters for an interface", "network,counters", 0),
    ("Linux", "Network", "Flush ARP cache", "ip neigh flush all",
     "Clear ARP/neighbor table", "network,arp,clear", 0),

    # ---- Linux / System ------------------------------------------------------
    ("Linux", "System", "System uptime", "uptime",
     "Load averages and uptime", "system,performance", 1),
    ("Linux", "System", "CPU info", "lscpu",
     "Processor architecture and core count", "system,cpu", 0),
    ("Linux", "System", "Memory usage", "free -h",
     "RAM and swap usage", "system,memory,performance", 1),
    ("Linux", "System", "Process list (top)", "top -bn1 | head -20",
     "Snapshot of running processes", "system,process", 0),
    ("Linux", "System", "Process list (htop)", "htop",
     "Interactive process manager", "system,process", 0),
    ("Linux", "System", "Kill process by name", "pkill -f {process_name}",
     "Kill process matching a name pattern", "system,process", 0),
    ("Linux", "System", "Find process by port", "ss -tulnp | grep :{port}",
     "Find which process listens on a port", "network,process,port", 1),
    ("Linux", "System", "Kernel version", "uname -r",
     "Current kernel version", "system,kernel", 0),
    ("Linux", "System", "OS release", "cat /etc/os-release",
     "Distribution and version info", "system,os", 0),
    ("Linux", "System", "Last logins", "last -n 20",
     "Recent login history", "system,security,auth", 0),
    ("Linux", "System", "Failed SSH logins", "grep 'Failed password' /var/log/auth.log | tail -20",
     "Recent failed SSH attempts", "system,security,ssh", 0),
    ("Linux", "System", "Journal errors", "journalctl -p err -n 50 --no-pager",
     "Last 50 error-level journal entries", "system,logs", 1),
    ("Linux", "System", "Systemctl service status", "systemctl status {service}",
     "Status of a systemd service", "system,service,systemd", 1),
    ("Linux", "System", "Restart service", "systemctl restart {service}",
     "Restart a systemd service", "system,service,systemd", 0),
    ("Linux", "System", "Enable service", "systemctl enable --now {service}",
     "Enable and start a service", "system,service,systemd", 0),
    ("Linux", "System", "List failed services", "systemctl --failed",
     "Show all failed systemd units", "system,service,systemd", 1),

    # ---- Linux / Files -------------------------------------------------------
    ("Linux", "Files", "Find file by name", "find {path} -name '{filename}'",
     "Recursive file search by name", "files,find", 0),
    ("Linux", "Files", "Find large files", "find {path} -type f -size +{size}M -exec ls -lh {} \\; | sort -k5 -rh | head -20",
     "Find files larger than N MB", "files,disk,find", 0),
    ("Linux", "Files", "Search in files", "grep -rn '{pattern}' {path}",
     "Recursive text search", "files,grep,search", 0),
    ("Linux", "Files", "Tail log", "tail -f {logfile}",
     "Follow a log file in real time", "files,logs", 1),
    ("Linux", "Files", "Archive directory", "tar -czf {archive}.tar.gz {directory}",
     "Compress a directory", "files,archive", 0),
    ("Linux", "Files", "Extract archive", "tar -xzf {archive}.tar.gz -C {destination}",
     "Extract a .tar.gz archive", "files,archive", 0),

    # ---- Linux / SSH ---------------------------------------------------------
    ("Linux", "SSH", "SSH to host", "ssh {user}@{host}",
     "Open SSH session", "ssh,remote", 1),
    ("Linux", "SSH", "SSH with key", "ssh -i {key_path} {user}@{host}",
     "SSH with a specific private key", "ssh,remote,key", 0),
    ("Linux", "SSH", "SCP file to remote", "scp {local_file} {user}@{host}:{remote_path}",
     "Copy file to remote host", "ssh,scp,transfer", 0),
    ("Linux", "SSH", "SCP file from remote", "scp {user}@{host}:{remote_file} {local_path}",
     "Copy file from remote host", "ssh,scp,transfer", 0),
    ("Linux", "SSH", "SSH tunnel (local)", "ssh -L {local_port}:{remote_host}:{remote_port} {user}@{jump_host}",
     "Local port forward via SSH", "ssh,tunnel,network", 0),

    # ---- Proxmox -------------------------------------------------------------
    ("Proxmox", "VM", "List all VMs", "qm list",
     "All virtual machines and status", "proxmox,vm,qemu", 1),
    ("Proxmox", "VM", "VM status", "qm status {vmid}",
     "Status of a specific VM", "proxmox,vm", 0),
    ("Proxmox", "VM", "Start VM", "qm start {vmid}",
     "Start a virtual machine", "proxmox,vm,start", 0),
    ("Proxmox", "VM", "Stop VM (graceful)", "qm shutdown {vmid}",
     "Graceful shutdown via ACPI", "proxmox,vm,stop", 0),
    ("Proxmox", "VM", "Stop VM (force)", "qm stop {vmid}",
     "Force stop a VM immediately", "proxmox,vm,stop", 0),
    ("Proxmox", "VM", "Reset VM", "qm reset {vmid}",
     "Hard reset a VM", "proxmox,vm", 0),
    ("Proxmox", "VM", "VM config", "qm config {vmid}",
     "Show VM configuration", "proxmox,vm,config", 0),
    ("Proxmox", "VM", "VM monitor command", "qm monitor {vmid}",
     "Open QEMU monitor for a VM", "proxmox,vm,debug", 0),
    ("Proxmox", "VM", "Clone VM", "qm clone {vmid} {newid} --name {name} --full",
     "Full clone of a VM", "proxmox,vm,clone", 0),
    ("Proxmox", "VM", "Create VM snapshot", "qm snapshot {vmid} {snapname}",
     "Create a named snapshot", "proxmox,vm,snapshot,backup", 1),
    ("Proxmox", "VM", "Rollback snapshot", "qm rollback {vmid} {snapname}",
     "Restore VM to a snapshot", "proxmox,vm,snapshot,restore", 0),
    ("Proxmox", "VM", "Delete snapshot", "qm delsnapshot {vmid} {snapname}",
     "Remove a VM snapshot", "proxmox,vm,snapshot", 0),
    ("Proxmox", "VM", "Destroy VM", "qm destroy {vmid} --purge",
     "Delete VM and all disks", "proxmox,vm,delete", 0),

    # ---- Proxmox / Container -------------------------------------------------
    ("Proxmox", "Container", "List all containers", "pct list",
     "All LXC containers and state", "proxmox,lxc,container", 1),
    ("Proxmox", "Container", "Container status", "pct status {ctid}",
     "Status of a specific container", "proxmox,lxc", 0),
    ("Proxmox", "Container", "Start container", "pct start {ctid}",
     "Start an LXC container", "proxmox,lxc,start", 0),
    ("Proxmox", "Container", "Stop container", "pct stop {ctid}",
     "Stop an LXC container", "proxmox,lxc,stop", 0),
    ("Proxmox", "Container", "Container config", "pct config {ctid}",
     "Show container configuration", "proxmox,lxc,config", 0),
    ("Proxmox", "Container", "Enter container", "pct enter {ctid}",
     "Shell into a running container", "proxmox,lxc,shell", 1),

    # ---- Proxmox / Storage ---------------------------------------------------
    ("Proxmox", "Storage", "List storages", "pvesm status",
     "All storage pools and usage", "proxmox,storage", 1),
    ("Proxmox", "Storage", "List storage content", "pvesm list {storage}",
     "Content of a specific storage", "proxmox,storage", 0),
    ("Proxmox", "Storage", "Ceph status", "ceph status",
     "Ceph cluster health and PG status", "proxmox,ceph,storage", 1),
    ("Proxmox", "Storage", "Ceph OSD tree", "ceph osd tree",
     "OSD hierarchy and status", "proxmox,ceph,osd", 0),
    ("Proxmox", "Storage", "Ceph OSD usage", "ceph osd df",
     "Per-OSD disk usage", "proxmox,ceph,storage", 0),
    ("Proxmox", "Storage", "Ceph pool stats", "ceph df",
     "Pool usage statistics", "proxmox,ceph,storage", 0),
    ("Proxmox", "Storage", "Ceph health detail", "ceph health detail",
     "Detailed health warning info", "proxmox,ceph,health", 1),

    # ---- Proxmox / Cluster ---------------------------------------------------
    ("Proxmox", "Cluster", "Cluster status", "pvecm status",
     "Cluster quorum and node state", "proxmox,cluster,ha", 1),
    ("Proxmox", "Cluster", "Node list", "pvecm nodes",
     "All cluster nodes", "proxmox,cluster", 0),
    ("Proxmox", "Cluster", "HA status", "ha-manager status",
     "High availability group and resource state", "proxmox,ha,cluster", 1),
    ("Proxmox", "Cluster", "Cluster tasks", "pvesr list",
     "Replication jobs status", "proxmox,cluster,replication", 0),

    # ---- Proxmox / Backup ----------------------------------------------------
    ("Proxmox", "Backup", "List backups", "pvesm list {storage} --content backup",
     "All backups in a storage", "proxmox,backup", 1),
    ("Proxmox", "Backup", "Backup VM now", "vzdump {vmid} --storage {storage} --mode snapshot",
     "Immediate VM backup (snapshot mode)", "proxmox,backup,vm", 0),
    ("Proxmox", "Backup", "Backup container now", "vzdump {ctid} --storage {storage} --mode snapshot",
     "Immediate container backup", "proxmox,backup,lxc", 0),

    # ---- Ansible -------------------------------------------------------------
    ("Ansible", "Playbook", "Run playbook", "ansible-playbook {playbook}.yml -i {inventory}",
     "Execute a playbook against an inventory", "ansible,playbook", 1),
    ("Ansible", "Playbook", "Run playbook (verbose)", "ansible-playbook {playbook}.yml -i {inventory} -vvv",
     "Playbook with full debug output", "ansible,playbook,debug", 0),
    ("Ansible", "Playbook", "Run playbook (check)", "ansible-playbook {playbook}.yml -i {inventory} --check",
     "Dry run - no changes applied", "ansible,playbook,dryrun", 1),
    ("Ansible", "Playbook", "Run playbook (diff)", "ansible-playbook {playbook}.yml -i {inventory} --diff",
     "Show what would change", "ansible,playbook,diff", 0),
    ("Ansible", "Playbook", "Limit to host", "ansible-playbook {playbook}.yml -i {inventory} --limit {host}",
     "Run playbook on a single host", "ansible,playbook,limit", 0),
    ("Ansible", "Playbook", "Run specific tag", "ansible-playbook {playbook}.yml -i {inventory} --tags {tag}",
     "Only tasks with a specific tag", "ansible,playbook,tag", 0),
    ("Ansible", "Playbook", "Skip tag", "ansible-playbook {playbook}.yml -i {inventory} --skip-tags {tag}",
     "Skip tasks with a specific tag", "ansible,playbook,tag", 0),

    # ---- Ansible / Ad-hoc ----------------------------------------------------
    ("Ansible", "Ad-hoc", "Ping all hosts", "ansible all -i {inventory} -m ping",
     "Connectivity test for all hosts", "ansible,adhoc,ping", 1),
    ("Ansible", "Ad-hoc", "Run shell command", "ansible {host_group} -i {inventory} -m shell -a '{command}'",
     "Run arbitrary shell command on hosts", "ansible,adhoc,shell", 0),
    ("Ansible", "Ad-hoc", "Copy file", "ansible {host_group} -i {inventory} -m copy -a 'src={src} dest={dest}'",
     "Push a file to remote hosts", "ansible,adhoc,copy", 0),
    ("Ansible", "Ad-hoc", "Gather facts", "ansible {host} -i {inventory} -m gather_facts",
     "Collect host facts", "ansible,adhoc,facts", 0),
    ("Ansible", "Ad-hoc", "Service restart", "ansible {host_group} -i {inventory} -m service -a 'name={service} state=restarted'",
     "Restart a service via ad-hoc", "ansible,adhoc,service", 0),

    # ---- Ansible / Inventory -------------------------------------------------
    ("Ansible", "Inventory", "List all hosts", "ansible all -i {inventory} --list-hosts",
     "Print all hosts in inventory", "ansible,inventory", 1),
    ("Ansible", "Inventory", "List group hosts", "ansible {group} -i {inventory} --list-hosts",
     "Print hosts in a specific group", "ansible,inventory", 0),
    ("Ansible", "Inventory", "Inventory graph", "ansible-inventory -i {inventory} --graph",
     "Visual tree of inventory groups", "ansible,inventory", 0),
    ("Ansible", "Inventory", "Host variables", "ansible-inventory -i {inventory} --host {host}",
     "All variables for a specific host", "ansible,inventory,vars", 0),

    # ---- Ansible / Galaxy / Vault --------------------------------------------
    ("Ansible", "Galaxy", "Install role", "ansible-galaxy install {role}",
     "Install a role from Ansible Galaxy", "ansible,galaxy,role", 0),
    ("Ansible", "Galaxy", "Install requirements", "ansible-galaxy install -r requirements.yml",
     "Install all roles from requirements file", "ansible,galaxy,role", 1),
    ("Ansible", "Vault", "Encrypt file", "ansible-vault encrypt {file}",
     "Encrypt a file with Ansible Vault", "ansible,vault,security", 0),
    ("Ansible", "Vault", "Decrypt file", "ansible-vault decrypt {file}",
     "Decrypt a Vault-encrypted file", "ansible,vault,security", 0),
    ("Ansible", "Vault", "Edit encrypted file", "ansible-vault edit {file}",
     "Edit an encrypted Vault file in-place", "ansible,vault,security", 0),
    ("Ansible", "Vault", "View encrypted file", "ansible-vault view {file}",
     "View (without editing) Vault file", "ansible,vault,security", 0),
]


def init_db(drop_existing: bool = False) -> None:
    if drop_existing and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing DB: {DB_PATH}")

    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)
    con.commit()

    cur = con.cursor()
    cur.executemany(
        "INSERT INTO commands(category, subcategory, title, command, description, tags, is_favorite) "
        "VALUES (?,?,?,?,?,?,?)",
        SEED_DATA,
    )
    con.commit()
    count = con.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
    con.close()
    print(f"DB ready: {DB_PATH}")
    print(f"Commands loaded: {count}")


if __name__ == "__main__":
    import sys
    drop = "--reset" in sys.argv
    init_db(drop_existing=drop)
