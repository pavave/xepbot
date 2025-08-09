// SPDX-License-Identifier: MIT
pragma solidity ^0.8.17;

interface IERC20 {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}

contract MinimalPaymentReceiver {
    address public owner;
    IERC20 public token;      // USDC token address
    uint256 public price;     // price in token's smallest units (e.g. USDC 6 decimals)

    mapping(address => bool) public paid;

    event Paid(address indexed payer, uint256 amount, string reference);
    event PriceUpdated(uint256 newPrice);
    event Withdraw(address indexed to, uint256 amount);

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }

    constructor(address _token, uint256 _price) {
        owner = msg.sender;
        token = IERC20(_token);
        price = _price;
    }

    /// @notice payer must first approve(this, price) on token contract
    function pay(string calldata reference) external {
        require(!paid[msg.sender], "Already paid");
        require(token.transferFrom(msg.sender, address(this), price), "Payment failed");
        paid[msg.sender] = true;
        emit Paid(msg.sender, price, reference);
    }

    function setPrice(uint256 _price) external onlyOwner {
        price = _price;
        emit PriceUpdated(_price);
    }

    function withdraw(address to, uint256 amount) external onlyOwner {
        // withdraw tokens from contract to owner-controlled address
        // We use transferFrom pattern on token; for withdrawing, will call token's transfer via low-level (assume token supports it)
        // Caller (owner) must ensure token transfer contract supports transfer to 'to'
        (bool ok, ) = address(token).call(abi.encodeWithSignature("transfer(address,uint256)", to, amount));
        require(ok, "Withdraw failed");
        emit Withdraw(to, amount);
    }
}
