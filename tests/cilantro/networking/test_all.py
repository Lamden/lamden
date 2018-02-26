from cilantro import config


m_ip = config['db'].get('ip')
m_int_port = config['db'].get('internal_port')
m_ext_port = config['db'].get('external_port')

d_ip = config['db'].get('ip')
d_port = config['db'].get('port')

w_ip = config['witness'].get('ip')