#include <SFML/Graphics.hpp>
#include <array>
#include <boost/tokenizer.hpp>
#include <cmath>
#include <cstring>
#include <fstream>
#include <iostream>
#include <vector>

#define FRAME_RATE 30
#define MAX_STR_LEN 1024

// Dual pendulum state: t, x1, v1, phi1, omega1, x2, v2, phi2, omega2, distance, collision
struct DualState {
    double t;
    double x1, v1, phi1, omega1;
    double x2, v2, phi2, omega2;
    double distance;
    int collision;
};

typedef std::vector<DualState> dual_state_sequence_t;

char pathCSVFile[MAX_STR_LEN];

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
    std::cerr << "Usage: " << prog << std::endl;
    std::cerr << "-f: DUAL_STATE_FILE (output from simulate-lqr-dual)" << std::endl;
}

bool read_states(const char *path, dual_state_sequence_t &states)
{
    std::ifstream infile(path);

    if (!infile.is_open())
    {
        perror("Could not open states file");
        return false;
    }

    std::string line;
    while (std::getline(infile, line))
    {
        if (line.empty())
            continue;
        if (line.rfind("#", 0) == 0)
            continue;

        boost::char_separator<char> sep(",");
        boost::tokenizer<boost::char_separator<char>> tokens(line, sep);

        DualState state;
        unsigned int col = 0;

        for (const auto &token : tokens)
        {
            double d = strtod(token.c_str(), NULL);
            switch (col)
            {
            case 0: state.t = d; break;
            case 1: state.x1 = d; break;
            case 2: state.v1 = d; break;
            case 3: state.phi1 = d; break;
            case 4: state.omega1 = d; break;
            case 5: state.x2 = d; break;
            case 6: state.v2 = d; break;
            case 7: state.phi2 = d; break;
            case 8: state.omega2 = d; break;
            case 9: state.distance = d; break;
            case 10: state.collision = (int)d; break;
            }
            col++;
        }

        if (col < 11)
        {
            std::cerr << "Too few tokens in line: " << line << std::endl;
            return false;
        }

        states.push_back(state);
    }

    return true;
}

void prepare_states_vis(const dual_state_sequence_t &states, dual_state_sequence_t &states_vis)
{
    double period = 1.0 / FRAME_RATE;
    double t = 0.0;

    for (const DualState &state : states)
    {
        if (state.t >= t)
        {
            states_vis.push_back(state);
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

    dual_state_sequence_t states;
    dual_state_sequence_t states_vis;

    if (!read_states(pathCSVFile, states))
    {
        exit(1);
    }

    prepare_states_vis(states, states_vis);

    // Wider window to accommodate two pendulums
    sf::RenderWindow window(sf::VideoMode(1280, 520), "Dual Inverted Pendulum");

    // Load font
    sf::Font font;
    if (!font.loadFromFile("../asset/FreeSansBold.ttf"))
    {
        std::cerr << "Failed to load font!\n";
    }

    // Colors
    const sf::Color grey = sf::Color(0x7E, 0x7E, 0x7E);
    const sf::Color light_grey = sf::Color(0xAA, 0xAA, 0xAA);
    const sf::Color brown = sf::Color(0xCC, 0x99, 0x66);
    const sf::Color blue = sf::Color(0x33, 0x66, 0x99);
    const sf::Color red = sf::Color(0xCC, 0x33, 0x33);
    const sf::Color green = sf::Color(0x33, 0x99, 0x33);

    // Time display
    sf::Text timeText;
    timeText.setFont(font);
    timeText.setCharacterSize(24);
    timeText.setFillColor(grey);
    timeText.setPosition(20.0F, 420.0F);

    // Distance display
    sf::Text distText;
    distText.setFont(font);
    distText.setCharacterSize(24);
    distText.setFillColor(grey);
    distText.setPosition(20.0F, 450.0F);

    // Collision status
    sf::Text statusText;
    statusText.setFont(font);
    statusText.setCharacterSize(28);
    statusText.setPosition(20.0F, 480.0F);

    // Labels for pendulums
    sf::Text label1, label2;
    label1.setFont(font);
    label1.setCharacterSize(18);
    label1.setFillColor(sf::Color::Black);
    label1.setString("P1");

    label2.setFont(font);
    label2.setCharacterSize(18);
    label2.setFillColor(blue);
    label2.setString("P2");

    // Track - spans from x=-0.5 to x=10 in simulation coordinates
    sf::RectangleShape track(sf::Vector2f(1100.0F, 4.0F));
    track.setOrigin(0.0F, 2.0F);
    track.setPosition(150.0F, 280.0F);  // starts at x=-0.5 (200-50=150)
    track.setFillColor(light_grey);

    // Cart 1 (black)
    sf::RectangleShape cart1(sf::Vector2f(80.0F, 60.0F));
    cart1.setOrigin(40.0F, 30.0F);
    cart1.setFillColor(sf::Color::Black);

    // Pole 1 (brown)
    sf::RectangleShape pole1(sf::Vector2f(16.0F, 160.0F));
    pole1.setOrigin(8.0F, 160.0F);
    pole1.setFillColor(brown);

    // Cart 2 (blue)
    sf::RectangleShape cart2(sf::Vector2f(80.0F, 60.0F));
    cart2.setOrigin(40.0F, 30.0F);
    cart2.setFillColor(blue);

    // Pole 2 (darker brown)
    sf::RectangleShape pole2(sf::Vector2f(16.0F, 160.0F));
    pole2.setOrigin(8.0F, 160.0F);
    pole2.setFillColor(sf::Color(0x99, 0x66, 0x33));

    // Distance indicator line
    sf::RectangleShape distLine(sf::Vector2f(1.0F, 4.0F));
    distLine.setFillColor(green);

    // Scale: 100 pixels per meter, origin shifted left so x=0-8 range fits on screen
    const float SCALE = 100.0F;
    const float CENTER_X = 200.0F;  // x=0 at 200px, x=7 at 900px
    const float TRACK_Y = 280.0F;

    sf::Clock clock;
    dual_state_sequence_t::iterator it = states_vis.begin();

    while (window.isOpen() && it != states_vis.end())
    {
        sf::Event event;
        while (window.pollEvent(event))
        {
            if (event.type == sf::Event::Closed)
                window.close();
        }

        DualState state = *it;
        it++;

        // Wait for frame timing
        sf::Time time;
        uint64_t time_us;
        uint64_t frame_time_us;
        do
        {
            time = clock.getElapsedTime();
            time_us = time.asMicroseconds();
            frame_time_us = (uint64_t)(1000000.0 * state.t);
        } while (time_us < frame_time_us);

        // Update text displays
        float time_sec = time.asSeconds();
        std::string timeMsg = std::to_string(time_sec);
        timeText.setString("Time: " + timeMsg.substr(0, timeMsg.find('.') + 3) + " s");

        std::string distMsg = std::to_string(state.distance);
        distText.setString("Distance: " + distMsg.substr(0, distMsg.find('.') + 3) + " m");

        if (state.collision)
        {
            statusText.setString("COLLISION!");
            statusText.setFillColor(red);
        }
        else
        {
            statusText.setString("Safe");
            statusText.setFillColor(green);
        }

        // Calculate positions
        float x1_px = CENTER_X + SCALE * state.x1;
        float x2_px = CENTER_X + SCALE * state.x2;
        float phi1_deg = to_deg(state.phi1);
        float phi2_deg = to_deg(state.phi2);

        // Update cart and pole positions
        cart1.setPosition(x1_px, TRACK_Y);
        pole1.setPosition(x1_px, TRACK_Y);
        pole1.setRotation(-phi1_deg);

        cart2.setPosition(x2_px, TRACK_Y);
        pole2.setPosition(x2_px, TRACK_Y);
        pole2.setRotation(-phi2_deg);

        // Update labels
        label1.setPosition(x1_px - 10, TRACK_Y + 40);
        label2.setPosition(x2_px - 10, TRACK_Y + 40);

        // Update distance line
        float dist_px = std::abs(x2_px - x1_px);
        distLine.setSize(sf::Vector2f(dist_px, 4.0F));
        distLine.setPosition(std::min(x1_px, x2_px), TRACK_Y + 60);
        if (state.collision)
            distLine.setFillColor(red);
        else
            distLine.setFillColor(green);

        // Draw everything
        window.clear(sf::Color::White);
        window.draw(track);
        window.draw(distLine);
        window.draw(cart1);
        window.draw(pole1);
        window.draw(cart2);
        window.draw(pole2);
        window.draw(label1);
        window.draw(label2);
        window.draw(timeText);
        window.draw(distText);
        window.draw(statusText);
        window.display();
    }

    // Keep window open after animation ends
    while (window.isOpen())
    {
        sf::Event event;
        while (window.pollEvent(event))
        {
            if (event.type == sf::Event::Closed)
                window.close();
        }
    }

    return 0;
}
