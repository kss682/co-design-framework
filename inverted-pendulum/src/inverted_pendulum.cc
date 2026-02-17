#include "inverted_pendulum.h"
#include <boost/numeric/odeint.hpp>

typedef boost::numeric::odeint::runge_kutta4<pendulum_state_t> rk4;

// Gravity [m/s^2]
const double g = 9.8067;

class Observer
{
  public:
    Observer(state_sequence_t &states);

    void operator()(const pendulum_state_t &x, const double t);

  private:
    state_sequence_t &states;
};

Observer::Observer(state_sequence_t &states) : states(states)
{
}

void Observer::operator()(const pendulum_state_t &x, const double t)
{
    time_state_t ts(t, x);
    states.push_back(ts);
}

void InvertedPendulum::operator()(const pendulum_state_t &x, pendulum_state_t &dxdt, const double)
{
    double vx = x[1];
    double theta = x[2];
    double omega = x[3];

    double s_t = std::sin(theta);
    double c_t = std::cos(theta);
    double o_2 = std::pow(omega, 2);
    double l_2 = std::pow(l, 2);

    double J_t = I + (m * l_2);
    double M_t = M + m;

    dxdt[0] = x[1];
    dxdt[1] = (-m * l * s_t * o_2 - m * g * (m * l_2 / J_t) * s_t * c_t + F) / (M_t - m * (m * l_2 / J_t) * c_t * c_t);
    dxdt[2] = x[3];
    dxdt[3] =
        (-m * l_2 * s_t * c_t * o_2 + M_t * g * l * s_t - l * c_t * F) / (J_t * (M_t / m) - m * (l * c_t) * (l * c_t));
}

InvertedPendulum::InvertedPendulum(double m, double M, double I, double l, double F, pendulum_state_t state)
    : m(m), M(M), I(I), l(l), F(F), t(0.0)
{
    this->state = state;
}

const pendulum_state_t &InvertedPendulum::get_state() const
{
    return state;
}

double InvertedPendulum::get_time() const
{
    return t;
}

double InvertedPendulum::get_force() const
{
    return F;
}

void InvertedPendulum::set_force(double f)
{
    F = f;
}

void InvertedPendulum::simulate(double d, double dt, state_sequence_t &states)
{
    Observer observer(states);

    integrate_const(rk4(), *this, state, t, t + d, dt, observer);

    // Simulation ends at last timestamp of last state.
    // Simulation might not end exactly at time t+d, but
    // at some time t' with t+d - dt < t' <= t+d.
    t = states.back().first;
}

void InvertedPendulum::simulate(double dt, state_sequence_t &states)
{
    Observer observer(states);

    rk4().do_step(*this, state, t, dt);

    observer(state, t);

    t += dt;
}
