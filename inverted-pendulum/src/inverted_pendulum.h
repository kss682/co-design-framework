#ifndef INVERTED_PENDULUM_H
#define INVERTED_PENDULUM_H

#include <array>
#include <vector>

/**
 * State of the pendulum system:
 *
 * [  x  ]
 * [  v  ]
 * [ phi ]
 * [omega]
 */
typedef std::array<double, 4> pendulum_state_t;
typedef std::pair<double, pendulum_state_t> time_state_t;
typedef std::vector<time_state_t> state_sequence_t;

class InvertedPendulum
{
  public:
    /**
     * @param m mass of pendulum [kg]
     * @param M mass of cart [kg]
     * @param I moment of inertia [kg*m^2]
     * @param l length of pendulum to center of mass [m]
     * @param F initial force onto cart [N]
     * @param state: initial state of the pendulum
     */
    InvertedPendulum(double m, double M, double I, double l, double F, pendulum_state_t state);

    /**
     * Get current system state (after the last time step).
     */
    const pendulum_state_t &get_state() const;

    /**
     * Get the current time of the simulation to which the current state applies.
     * Time advances by calling the function simulate().
     *
     * @return time [s]
     */
    double get_time() const;

    /**
     * Get the current force.
     *
     * @return force [N]
     */
    double get_force() const;

    /**
     * Set the current force.
     *
     * @param f force [N]
     */
    void set_force(double f);

    /**
     * Simulate the system for a given duration starting at the current time and state.
     *
     * The force onto the cart is constant during the simulation.
     *
     * Simulation might not end exactly at time t+d, but at some
     * time t' with t+d - dt < t' <= t+d.
     *
     * @param d duration of simulation [s]
     * @param dt step size of simulation [s]
     * @param states output will be added to states as ordered sequence of states with timestamps, approximately one
     * state per interval dt.
     */
    void simulate(double d, double dt, state_sequence_t &states);

    /**
     * Simulate the system for one step.
     *
     * @param dt step size of simulation [s]
     * @param states output will be added to states as ordered sequence of states with timestamps, approximately one
     * state per interval dt.
     */
    void simulate(double dt, state_sequence_t &states);

    /**
     * Functor: object can be called by boost::odeint to calculate the derivatives dxdt
     * of the equations of motion.
     *
     * @param x: current state
     * @param dxdt: derivatives
     * @param t: current time (not required here)
     */
    void operator()(const pendulum_state_t &x, pendulum_state_t &dxdt, const double t);

  private:
    const double m;
    const double M;
    const double I;
    const double l;

    double F;
    double t;

    pendulum_state_t state;
};

#endif
