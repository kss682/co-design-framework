#include <SFML/Graphics.hpp>
#include <array>
#include <boost/tokenizer.hpp>
#include <cmath>
#include <cstring>
#include <fstream>
#include <iostream>
#include <vector>

#include "inverted_pendulum.h"

#define FRAME_RATE 30

#define MAX_STR_LEN 1024

char pathCSVFile[MAX_STR_LEN];

/**
 * Parse command line arguments as passed to main() and store them in
 * global variables.
 */
int parse_cmdline_args(int argc, char *argv[])
{
    int opt;

    memset(pathCSVFile, 0, MAX_STR_LEN);

    while ((opt = getopt(argc, argv, "f:")) != -1)
    {
        switch (opt)
        {
        case 'f':
            strncpy(pathCSVFile, optarg, MAX_STR_LEN - 1);
            break;
        case ':':
        case '?':
        default:
            return -1;
        }
    }

    if (strlen(pathCSVFile) == 0)
        return -1;

    return 0;
}

void usage(const char *prog)
{
    std::cerr << "Usage:" << prog << std::endl;
    std::cerr << "-f: STATE_FILE" << std::endl;
}

bool read_states(const char *path, state_sequence_t &states_vis)
{
    std::ifstream infile(path);

    if (!infile.is_open())
    {
        perror("Could not open states file");
        return -1;
    }

    std::string line;
    while (std::getline(infile, line))
    {
        // Ignore empty lines with no characters
        if (line.empty())
            continue;
        // Ignore lines starting with #
        if (line.rfind("#", 0) == 0)
            continue;
        boost::char_separator<char> sep(",");
        boost::tokenizer<boost::char_separator<char>> tokens(line, sep);
        unsigned int token_cnt = 0;
        time_state_t time_state;
        for (const auto &token : tokens)
        {
            double d = strtod(token.c_str(), NULL);
            if (token_cnt == 0)
            {
                time_state.first = d;
            }
            else
            {
                time_state.second[token_cnt - 1] = d;
            }
            token_cnt++;
            if (token_cnt > 5)
            {
                std::cerr << "Too many tokens in line: " << line << std::endl;
                return false;
            }
        }
        if (token_cnt < 5)
        {
            std::cerr << "Too few tokens" << std::endl;
            return false;
        }
        assert(token_cnt == 5);
        states_vis.push_back(time_state);
    }

    return true;
}

void prepare_states_vis(const state_sequence_t &states, state_sequence_t &states_vis)
{
    double period = 1.0 / FRAME_RATE;
    double t = 0.0;

    for (time_state_t time_state : states)
    {
        if (time_state.first > t)
        {
            states_vis.push_back(time_state);
            t += period;
        }
    }
}

double to_deg(float rad)
{
    return rad * (180.0 / M_PI);
}

int main(int argc, char *argv[])
{
    if (parse_cmdline_args(argc, argv) == -1)
    {
        usage(argv[0]);
        exit(1);
    }

    state_sequence_t states;
    state_sequence_t states_vis;

    if (!read_states(pathCSVFile, states))
    {
        exit(1);
    }

    prepare_states_vis(states, states_vis);

    sf::RenderWindow window(sf::VideoMode(1024, 480), "Inverted Pendulum");

    // Load font
    sf::Font font;
    if (!font.loadFromFile("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"))
    {
        std::cerr << "Failed to load font!\n";
    }

    // Create text to display simulation time
    sf::Text text;
    text.setFont(font);
    text.setCharacterSize(24);
    const sf::Color grey = sf::Color(0x7E, 0x7E, 0x7E);
    text.setFillColor(grey);
    text.setPosition(480.0F, 360.0F);

    // Create a track for the cart
    sf::RectangleShape track(sf::Vector2f(1024.0F, 2.0F));
    track.setOrigin(512.0F, 1.0F);
    track.setPosition(512.0F, 240.0F);
    const sf::Color light_grey = sf::Color(0xAA, 0xAA, 0xAA);
    track.setFillColor(light_grey);

    // Create the cart of the inverted pendulum
    sf::RectangleShape cart(sf::Vector2f(100.0F, 100.0F));
    cart.setOrigin(50.0F, 50.0F);
    cart.setPosition(320.0F, 240.0F);
    cart.setFillColor(sf::Color::Black);

    // Create the pole of the inverted pendulum
    sf::RectangleShape pole(sf::Vector2f(20.0F, 200.0F));
    pole.setOrigin(10.0F, 200.0F);
    const sf::Color brown = sf::Color(0xCC, 0x99, 0x66);
    pole.setFillColor(brown);

    // Create a clock to run the simulation
    sf::Clock clock;

    state_sequence_t::iterator it = states_vis.begin();

    while (window.isOpen() && it != states_vis.end())
    {
        sf::Event event;
        while (window.pollEvent(event))
        {
            switch (event.type)
            {
            case sf::Event::Closed:
                window.close();
                break;
            }
        }

        time_state_t time_state = *it;
        it++;

        // Wait until next frame is due.
        sf::Time time;
        uint64_t time_us;
        uint64_t frame_time_us;
        do
        {
            time = clock.getElapsedTime();
            time_us = time.asMicroseconds();
            frame_time_us = (uint64_t)(1000000.0 * time_state.first);
        } while (time_us < frame_time_us);

        // Update the simulation
        float time_sec = time.asSeconds();
        std::string msg = std::to_string(time_sec);
        text.setString("Time   " + msg.substr(0, msg.find('.') + 2));

        float cart_x = time_state.second[0];
        float pole_angle_deg = to_deg(time_state.second[2]);

        // Update SFML drawings
        cart.setPosition(320.0 + 100 * cart_x, 240.0);
        pole.setPosition(320.0 + 100 * cart_x, 240.0);
        pole.setRotation(-pole_angle_deg);

        window.clear(sf::Color::White);
        window.draw(track);
        window.draw(cart);
        window.draw(pole);
        window.draw(text);
        window.display();
    }

    return 0;
}
