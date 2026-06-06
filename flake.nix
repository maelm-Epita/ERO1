{
    description = "ERO1 devshell";

    inputs = {
        nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
    };
    outputs = {self, nixpkgs }:
        let 
            pkgs = nixpkgs.legacyPackages."x86_64-linux";
        in
            {
            devShells."x86_64-linux".default = pkgs.mkShell {
                packages = [ 
                    pkgs.python312
                ];
                shellHook = ''
                    echo "-------------------"
                    echo "Entered environment"
                '';
            };
        };
}
