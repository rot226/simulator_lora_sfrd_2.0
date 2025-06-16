import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from launcher.simulator import Simulator


def test_server_configuration():
    sim = Simulator(num_nodes=1, num_gateways=1, packets_to_send=1, adr_server=True)
    assert sim.network_server.adr_enabled is True
    assert sim.network_server.nodes == sim.nodes
    assert sim.network_server.gateways == sim.gateways
    assert sim.network_server.channel is sim.channel
