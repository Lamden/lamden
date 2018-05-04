class GroupMixin:
    def load_ips(self, ips):
        return {ip: {
            'ip': ip,
            'groups': []
        } for ip in ips}

    def update_group_idxs(self, key=None, max_group_size=32):
        old_ports = [self.groups[idx]['port'] for idx in self.idxs]
        new_idxs = []
        if self.mode == 'all_target_groups':
            new_idxs = list(self.nodes.keys())
        elif self.mode == 'random_subgroup':
            groups = self.nodes[key]['groups']
            new_idxs = [random.choice(groups)]
        elif self.mode == 'rolling_group':
            new_idxs = [self.curr_group]
            self.curr_group = (self.curr_group + 1) % len(self.groups)
        elif self.mode == 'random_group':
            new_idxs = [random.choice(self.groups)]
        new_ports = [self.groups[idx]['port'] for idx in new_idxs]
        self.idxs += new_idxs
        if len(old_ports) + len(new_ports) > max_group_size:
            self.idxs = self.idxs[-max_group_size:]
        return old_ports, new_ports

    def regroup(self, nodes, window_size=6, skip_space=2):
        if not hasattr(self, 'curr_group'): self.curr_group = 0
        self.groups = {}
        self.nodes = nodes
        groups_list = self.distribute_groups(window_size, skip_space)
        ports = {}
        for idx, group in enumerate(groups_list):
            # port = random_port(ports)
            port = 10000 + int(idx)
            ports[idx] = port
            for key in group:
                self.nodes[key]['groups'].append(idx)
                if not self.groups.get(idx):
                    self.groups[idx] = {'port': port, 'nodes': [], 'count': 0}
                self.groups[idx]['nodes'].append({
                    'key': key,
                    'ip': self.nodes[key]['ip']
                })
        return groups_list

    def distribute_groups(self, window_size, skip_space):
        keys = list(self.nodes.keys())
        keys = keys[(len(keys) - window_size) + 1:len(keys)] + keys
        zip_list = [keys[i:] for i in range(0, window_size, skip_space)]
        groups_list = list(zip(*zip_list))[:]
        return groups_list

if __name__ == '__main__':
    gmi = GroupMixin()
    nodes = gmi.load_ips(["172.29.5.1","172.29.5.2","172.29.5.3","172.29.5.4","172.29.5.5","172.29.5.6","172.29.5.7","172.29.5.8"])
    print(nodes)
