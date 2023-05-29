{ pkgs ? import<nixpkgs> {} }:

with pkgs;

mkShell {
    buildInputs = [ graphviz python39 python39Packages.pip python39Packages.virtualenv python39Packages.setuptools ];
}
