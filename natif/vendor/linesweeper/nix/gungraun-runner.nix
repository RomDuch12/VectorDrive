{
  fetchCrate,
  rustPlatform,
}:
rustPlatform.buildRustPackage rec {
  pname = "gungraun-runner";
  version = "0.17.0";
  src = fetchCrate {
    inherit pname version;
    sha256 = "sha256-l0leQxydZNbZImJfDUuF7RahT5N9QZLJ9egWalMiDCc=";
  };

  cargoHash = "sha256-nDqsW1O6q4F2pvFvH3evMUR4zjzcqrwlcyfFMQjWT5g=";
  doCheck = false;
}
