import os
import subprocess
import shutil

def run_test():
    test_out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'candy_output'))
    if os.path.exists(test_out_dir):
        shutil.rmtree(test_out_dir)
        
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'tools', 'golden_candy_spinner.py'))
    
    import sys
    # Run the spinner in mock mode with a small chunk size of 5MB
    cmd = [
        sys.executable, script_path, 
        "dummy_model.gguf", 
        test_out_dir, 
        "--chunk_size", "5", 
        "--mock"
    ]
    
    print("Running Golden Candy Spinner...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
        
    assert result.returncode == 0, "Golden Candy Spinner failed."
    
    # Verify outputs
    files = os.listdir(test_out_dir)
    print("Output files:", files)
    
    manifest_found = any(f.endswith(".tesseract_profiles.json") for f in files)
    chunks_found = any(f.endswith(".trf") for f in files)
    
    assert manifest_found, "Manifest file not found in output!"
    assert chunks_found, "TRF chunks not found in output!"
    
    # Read manifest to ensure elastic_breathing_search is true
    manifest_path = os.path.join(test_out_dir, "dummy_model.gguf.tesseract_profiles.json")
    import json
    with open(manifest_path, "r") as f:
        manifest = json.load(f)
        assert manifest["runtime_directives"]["elastic_breathing_search"] is True, "elastic_breathing_search directive missing or false!"
        
    print("\n[SUCCESS] Golden Candy Spinner integration test passed successfully!")

if __name__ == "__main__":
    run_test()
