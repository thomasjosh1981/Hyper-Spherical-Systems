#include "drm_manager.hpp"
#include <iostream>

#if defined(_WIN32)
#include <windows.h>
#else
#include <unistd.h>
#endif

namespace tesseract {

std::string DRMManager::generate_hwid() {
    // For MVP, generate a simple HWID based on hostname. 
    // In production, this reads Motherboard UUID via WMI / SMBIOS.
    char hostname[256] = {0};
#if defined(_WIN32)
    DWORD size = sizeof(hostname);
    GetComputerNameA(hostname, &size);
#else
    gethostname(hostname, sizeof(hostname));
#endif
    
    std::string hwid = "HWID-" + std::string(hostname);
    // Simple hash
    size_t hash = 0;
    for (char c : hwid) {
        hash = hash * 31 + c;
    }
    return "HWID-" + std::to_string(hash);
}

bool DRMManager::verify_license(const std::string& license_key) {
    // 1. Check for the Infinitix Easter Egg
    if (license_key == "INFINITIX-SHARE-THE-KNOWLEDGE") {
        std::cout << "\n=======================================================\n";
        std::cout << "You're welcome. Everyone should have access to every\n";
        std::cout << "bit of info available, but I still need to make a\n";
        std::cout << "living too. Either way, live your best life.\n";
        std::cout << "=======================================================\n\n";
        return true; // Bypass HWID check, grant PRO tier
    }
    
    // 2. Standard Cryptographic Check (Mock MVP)
    // In production, this uses ECDSA (secp256k1) to verify the signature of HWID
    std::string expected_key = "LICENSE-" + generate_hwid() + "-PRO";
    if (license_key == expected_key) {
        return true;
    }
    
    return false; // Invalid license, drop to FREE tier
}

} // namespace tesseract
