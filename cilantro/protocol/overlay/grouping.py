from cilantro.logger import get_logger
from cilantro.protocol.networks import *
from cilantro.protocol.networks.ip_util import *
import random

log = get_logger(__name__)

class Grouping:
    def __init__(self, mode='rolling_group', *args, **kwargs):
        self.mode = mode

    def regroup(self, nodes, group_size=3, skip_size=1, starting_port=10000, max_num_ports=10000):
        if not hasattr(self, 'curr_group'): self.curr_group = 0
        self.groups = {}
        self.nodes = load_ips(nodes)
        groups_list = self.distribute_groups(group_size, skip_size, starting_port, max_num_ports)
        ports = {}
        for idx, group in enumerate(groups_list):
            port = starting_port + int(idx)
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

    def designate_next_group(self, max_group_size=32):
        # Update the idxs so it will send to the ports that specific subscribers listens to
        old_ports, new_ports = self.update_group_idxs(key=None, max_group_size=max_group_size)
        log.debug('{},{}'.format(old_ports, new_ports))
        # remove any old ports that will not be in the resulting group
        #   ONLY IF it is above the max_group_size
        if len(old_ports) + len(new_ports) > max_group_size:
            for port in (old_ports+new_ports)[:-max_group_size]:
                self.composer.remove_pub(url="tcp://{}:{}".format(self.host, port))
        # add any new ports that is not already in the old ports
        for port in new_ports:
            self.composer.add_pub(url="tcp://{}:{}".format(self.host, port))

    def distribute_groups(self, group_size, skip_size, starting_port, max_num_ports):
        if not hasattr(self, 'nodes'):
            log.warn('Cannot send messages as groups have not been defined. Run regroup(node_ip_list) before trying to run designate_next_group()')
        else:
            assert skip_size >= 1, 'skip_size must be > 1'
            keys = list(self.nodes.keys())
            num_ports = min(len(keys), max_num_ports)
            assert group_size * skip_size <= num_ports, 'there are overlapping keys in the group'
            ports = {(starting_port+i):[] for i in range(num_ports)}
            for i in range(num_ports):
                ports[starting_port+i] = [keys[(i+j*skip_size)%num_ports] for j in range(group_size)]
            return ports.values()

    def update_group_idxs(self, key=None, max_group_size=32):
        log.debug(self.mode)
        if not hasattr(self, 'idxs'): self.idxs = []
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

# if __name__ == '__main__':
#     gmi = Grouping()
#     nodes = load_ips(["172.29.5.1","172.29.5.2","172.29.5.3","172.29.5.4","172.29.5.5","172.29.5.6","172.29.5.7","172.29.5.8"])
#     gmi.regroup(nodes)
#     mapsss = {}
#     for i in gmi.groups:
#         g = gmi.groups[i]
#         for item in g['nodes']:
#             if not mapsss.get(item['key']):
#                 mapsss[item['key']] = []
#             mapsss[item['key']].append(g['port'])
#     pp.pprint(gmi.groups)
#     pp.pprint(mapsss)
