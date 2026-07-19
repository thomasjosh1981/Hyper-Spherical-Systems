#include "gateway_scanner.hpp"
#include <iostream>

#if defined(_WIN32)
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#endif

namespace pirate {

GatewayScanner::GatewayScanner() = default;
GatewayScanner::~GatewayScanner() = default;

bool GatewayScanner::is_port_open(int port) {
#if defined(_WIN32)
    SOCKET s = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (s == INVALID_SOCKET) return false;
    
    // Set non-blocking
    u_long mode = 1;
    ioctlsocket(s, FIONBIO, &mode);
    
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    inet_pton(AF_INET, "127.0.0.1", &addr.sin_addr);
    
    connect(s, reinterpret_cast<sockaddr*>(&addr), sizeof(addr));
    
    fd_set fdset;
    FD_ZERO(&fdset);
    FD_SET(s, &fdset);
    
    timeval tv{};
    tv.tv_sec = 0;
    tv.tv_usec = 10000; // 10ms timeout
    
    int result = select(0, nullptr, &fdset, nullptr, &tv);
    closesocket(s);
    return (result == 1);
#else
    // Dummy for non-windows in this example
    return false;
#endif
}

std::vector<RoutingDirective> GatewayScanner::scan_for_gateways() {
    std::vector<RoutingDirective> endpoints;
    
    // 11434 = Ollama
    if (is_port_open(11434)) {
        RoutingDirective ollama;
        ollama.backend_name = "ollama";
        ollama.target_port = 11434;
        endpoints.push_back(ollama);
    }
    
    // 1234 = LM Studio
    if (is_port_open(1234)) {
        RoutingDirective lmstudio;
        lmstudio.backend_name = "lmstudio";
        lmstudio.target_port = 1234;
        endpoints.push_back(lmstudio);
    }
    
    // 8080 = llama.cpp / koboldcpp default
    if (is_port_open(8080)) {
        RoutingDirective kobold;
        kobold.backend_name = "koboldcpp";
        kobold.target_port = 8080;
        endpoints.push_back(kobold);
    }
    
    return endpoints;
}

} // namespace pirate
