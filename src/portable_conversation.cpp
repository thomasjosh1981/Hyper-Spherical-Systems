#include <string>
#include <iostream>
#include <fstream>
#include "universal_endpoint.hpp"

namespace hypersp {

class PortableConversation {
public:
    PortableConversation(UniversalEndpoint& endpoint) : endpoint_(endpoint) {}
    
    bool save_to_jump_drive(const std::string& filepath, const std::string& active_memory) {
        std::cout << "[PortableConversation] Exporting to universal UEP file format...\n";
        std::string sealed = endpoint_.seal_payload(active_memory);
        
        std::ofstream out(filepath, std::ios::binary);
        if (!out) {
            std::cerr << "[PortableConversation] Error writing to " << filepath << "\n";
            return false;
        }
        
        out.write(sealed.data(), sealed.size());
        std::cout << "[PortableConversation] Conversation safely exported to " << filepath << "\n";
        return true;
    }
    
    std::string load_from_jump_drive(const std::string& filepath) {
        std::cout << "[PortableConversation] Loading UEP from jump drive...\n";
        // mock load
        return endpoint_.unseal_payload("MOCK_SEALED_DATA");
    }

private:
    UniversalEndpoint& endpoint_;
};

} // namespace hypersp
