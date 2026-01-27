#include "lqr.h"
#include <cmath>

LQRegulator::LQRegulator(const pendulum_state_t &K) : K(K)
{
}

double LQRegulator::control(const pendulum_state_t state)
{
    // u = -K*state
    double u = -(K[0] * state[0] + K[1] * state[1] + K[2] * state[2] + K[3] * state[3]);

    return u;
}

double LQRegulator::control(const pendulum_state_t state, double pos)
{
    // u = -K*state + K[0]*reference_position
    double u = -(K[0] * state[0] - K[0] * pos + K[1] * state[1] + K[2] * state[2] + K[3] * state[3]);

    return u;
}

double LQRegulator::control(const pendulum_state_t state, const pendulum_state_t target_state){

    double u = -((state[0] - target_state[0])*K[0] + (state[1] - target_state[1])*K[1] + (state[2] - target_state[2])*K[2] + (state[3] - target_state[3])*K[3]);

    return u;
}