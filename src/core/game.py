import numba
import numpy as np

from src.core.random import poisson_clock
from src.core.vector2d import length_nx2


class SpatialGame(object):
    """Base class for spatial games"""

    def __init__(self):
        self.players = None
        self.strategies = None

    def best_response_strategy(self, *args, **kwargs):
        pass

    def update(self, *args, **kwargs):
        pass


@numba.jit(nopython=True)
def payoff(s_our, s_neighbor, time_aset, t_evac_i, t_evac_j):
    """Payout from game matrix.
    :param s_our: Our strategy
    :param s_neighbor: Neighbor strategy
    """
    if s_neighbor == 0:
        if s_our == 0:
            average = (t_evac_i + t_evac_j) / 2
            if average == 0:
                average = 4.0e-8
            return time_aset / average
        elif s_our == 1:
            return 1
    elif s_neighbor == 1:
        if s_our == 0:
            return -1
        elif s_our == 1:
            return 0
    else:
        raise ValueError("Not valid strategy.")


@numba.jit(nopython=True)
def best_response_strategy(players, agent, strategy, strategies, time_aset,
                           time_evac, interval, dt):
    """Best response strategy. Minimizes loss"""
    loss = np.zeros(2)  # values: loss, indices: strategy
    np.random.shuffle(players)
    # TODO: check if j not in players:
    for i in players:
        if poisson_clock(interval, dt):
            for j in agent.neighbors[i]:
                if j < 0:
                    continue
                for s_our in strategies:
                    loss[s_our] += payoff(s_our,
                                          strategy[j],
                                          time_aset,
                                          time_evac[i],
                                          time_evac[j])
            strategy[i] = np.argmin(loss)  # Update strategy
            loss[:] = 0  # Reset loss array
            # TODO: Update agents parameters by the new strategy


class EgressGame(object):
    attrs = (
        "strategies",
        "strategy",
        "t_aset_0",
        "t_evac",
        "interval",
    )

    def __init__(self, agent, exit_door, t_aset_0, interval, neighbor_radius,
                 neighborhood_size):
        """Patient and impatient pedestrians in a spatial game for egress
        congestion. Strategies are denoted: {0: "Impatient", 1: "Patient"}.

        :param agent: Agent class
        :param exit_door: Exit door class
        :param t_aset_0: Initial available safe egress time.
        :param interval: Interval for updating strategies
        """
        self.agent = agent
        self.agent.neighbor_radius = neighbor_radius
        self.agent.neighborhood_size = neighborhood_size
        self.agent.reset_neighbor()
        self.exit_door = exit_door

        self.strategies = np.array((0, 1), dtype=np.int64)
        self.strategy = np.ones(self.agent.size, dtype=np.int64)
        self.t_aset_0 = t_aset_0
        self.t_evac = np.zeros(self.agent.size)
        self.interval = interval

    def agent_closer_to_exit(self, players):
        # values: distances from the door
        dist = length_nx2(self.exit_door.mid - self.agent.position[players])
        # players[values] = agents, indices = number of agents closer to exit
        num = np.argsort(dist)
        # values = number of agents closer to exit, players[indices] = agents
        num = np.argsort(num)
        return num

    def update(self, t_simu, dt, t_aset=None):
        """Update strategies for all agents.
        :param dt: Timestep used by integrator to update simulation.
        """
        # TODO: Not include agent that have reached their goals
        # Indices of agents that are playing the game
        players = self.agent.indices()

        # Number of agents closer to the exit than agent i
        t_evac = self.agent_closer_to_exit(players) / self.exit_door.capacity
        if t_aset is None:
            t_aset = self.t_aset_0 - t_simu

        self.t_evac[:] = 0  # Reset
        self.t_evac[players] = t_evac  # Index time_evac by players

        # Loop over agents and update strategies
        best_response_strategy(players, self.agent, self.strategy,
                               self.strategies, t_aset, self.t_evac,
                               self.interval, dt)