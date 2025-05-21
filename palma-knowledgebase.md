# Palma Wallet Knowledge Base

## General Information

### What is Palma Wallet?
Palma Wallet is a cryptocurrency wallet application that allows users to securely store, send, and receive digital assets. It focuses on providing a user-friendly interface while maintaining robust security for cryptocurrency transactions.

### Which cryptocurrencies does Palma Wallet support?
Palma Wallet currently supports USDT (Tether) on both ERC20 (Ethereum) and TRC20 (TRON) networks. Support for additional cryptocurrencies is planned for future updates.

### Is Palma Wallet free to use?
Palma Wallet is free to download and use. There are no fees charged by the wallet itself for basic operations. However, blockchain transaction fees (network fees) apply when sending cryptocurrencies, which vary depending on the network used (ERC20 or TRC20).

## Account Management

### How do I create a Palma Wallet account?
You can create a Palma Wallet account by signing in with Google, Apple, or phone verification. After authentication, a secure cryptographic key pair is generated for your wallet to ensure transaction security.

### What authentication methods does Palma Wallet support?
Palma Wallet supports three authentication methods: Google Sign-In, Apple Sign-In, and phone number verification. These provide secure and convenient ways to access your wallet.

### How does Palma Wallet ensure the security of my account?
Palma Wallet implements several security measures including: generating cryptographic key pairs (public and private keys) for each user, securely storing private keys in encrypted storage on your device, using digital signatures to verify transaction authenticity, and providing backup options for your private keys protected by a password.

### What happens if I lose access to my device?
If you've created a backup of your private key in the Settings screen, you can restore your wallet on a new device using the backup and your password. Without a backup, you may lose access to your funds, so creating a secure backup is essential.

### How do I sign out of Palma Wallet?
You can sign out by either tapping the 'Sign Out' button in the header of the Home screen or by going to Settings > Account Actions > Sign Out. When you sign out, your wallet data is preserved locally to maintain access to your private keys and wallet information.

## Wallet Security

### How is my private key stored in Palma Wallet?
Your private key is stored securely using React Native's EncryptedStorage, which uses platform-specific encryption methods (Keychain on iOS and Keystore on Android). The private key never leaves your device unencrypted.

### How do I back up my wallet?
To back up your wallet: 1) Go to Settings, 2) Navigate to the 'Wallet Security' section, 3) Enter a strong password (minimum 8 characters), 4) Confirm your password, 5) Tap 'Secure Backup'. Store your backup password safely – without it, you cannot restore your wallet.

### What happens if I forget my backup password?
If you forget your backup password, you won't be able to restore your wallet from the backup. There is no password recovery mechanism for security reasons. This is why it's crucial to store your backup password in a safe and memorable place.

### How does transaction signing work in Palma Wallet?
Palma Wallet uses cryptographic signing for all transactions. When you initiate a transaction, the app creates a digital signature using your private key. This signature proves you authorized the transaction without exposing your private key. The signature is verified on the blockchain using your public key.

### Is my data synchronized across devices?
Your basic account information is stored on Palma's servers, but your private keys remain only on your device for security. If you want to use your wallet on multiple devices, you need to use the backup and restore functionality on each device.

## Cryptocurrency Transactions

### How do I send cryptocurrency with Palma Wallet?
To send cryptocurrency: 1) Tap the 'Send' button on the Home screen, 2) Enter the recipient's wallet address or scan their QR code, 3) Enter the amount you want to send, 4) Select the network (ERC20 or TRC20), 5) Review the transaction details including fees, 6) Confirm to send. The transaction will be processed on the blockchain.

### How do I receive cryptocurrency with Palma Wallet?
To receive cryptocurrency: 1) Tap the 'Receive' button on the Home screen, 2) Your wallet address will be displayed along with a QR code, 3) Share this address with the sender, 4) Make sure the sender uses the correct network (ERC20 or TRC20), 5) Once the transaction is confirmed on the blockchain, the funds will appear in your wallet.

### What's the difference between ERC20 and TRC20 networks?
ERC20 is the token standard on the Ethereum blockchain, while TRC20 is the standard on the TRON blockchain. The main differences include: 1) Transaction fees - ERC20 typically has higher fees, 2) Confirmation time - TRC20 is usually faster, 3) Security aspects - ERC20 is considered more established. Always ensure the sender and receiver are using the same network.

### How long do transactions take to complete?
Transaction times vary by network: 1) ERC20 (Ethereum) transactions typically take between 30 seconds to several minutes, depending on network congestion and the gas fee paid, 2) TRC20 (TRON) transactions are usually faster, taking approximately 15-30 seconds. These times are for blockchain confirmations, not including time needed to prepare and sign transactions.

### What are transaction fees and how do they work?
Transaction fees are payments to blockchain network validators who process transactions. 1) For ERC20 (Ethereum), fees are called 'gas fees' and can vary significantly based on network congestion, 2) For TRC20 (TRON), fees are typically much lower and more stable. Palma Wallet displays the expected fee before you confirm a transaction, allowing you to make an informed decision.

### What is the Swap feature in Palma Wallet?
The Swap feature allows you to exchange one cryptocurrency for another directly within the Palma Wallet app. It provides an easy way to convert between digital assets without using an external exchange. This feature will be expanded in future updates to support more currency pairs and better rates.

## Troubleshooting

### My transaction is pending for a long time. What should I do?
For long-pending transactions: 1) Check the network status - high congestion can delay processing, 2) For ERC20 transactions, the gas fee might be too low during high demand periods, 3) Verify your internet connection is stable, 4) Wait for blockchain confirmation - sometimes it takes longer during peak periods, 5) If the problem persists for more than a few hours, contact support with your transaction details.

### I sent funds to the wrong address. Can I get them back?
Unfortunately, blockchain transactions are irreversible once confirmed. If you sent funds to an incorrect address: 1) If you know the recipient, contact them directly to request a return transaction, 2) If you sent to an exchange or service, contact their customer support, 3) If you sent to a random address, recovery is generally not possible. Always double-check addresses before confirming transactions.

### Why can't I see my balance after receiving a transaction?
If your balance isn't updating: 1) Confirm the transaction has enough blockchain confirmations (check the explorer), 2) Verify you're checking the correct network (ERC20 vs TRC20), 3) Restart the app to refresh your balance, 4) Check if the sender has actually completed the transaction on their end, 5) If the transaction is confirmed on the blockchain but not showing in the app, contact support.

### The app crashes when I try to send a transaction. What should I do?
If the app crashes during transactions: 1) Update to the latest app version, 2) Restart your device, 3) Check your internet connection, 4) Make sure you have sufficient balance (including for transaction fees), 5) If the problem persists, try reinstalling the app (ensure you have your backup first!), 6) Contact support if none of these solutions work, providing details about your device and the circumstances of the crash.

## Technical Details

### What cryptographic methods does Palma Wallet use?
Palma Wallet uses RSA cryptography in its initial version, transitioning to FIO Protocol library in newer versions. These cryptographic methods are used for generating key pairs, signing transactions, and verifying signatures. The implementation includes proper key generation, secure signing procedures, and robust verification methods to ensure transaction security.

### How does Palma Wallet verify transaction signatures?
Palma Wallet verifies signatures using public key cryptography: 1) When a transaction is created, a digital signature is generated using the sender's private key, 2) The signature, along with the transaction data, is sent to the server, 3) The server retrieves the user's public key from the database, 4) Using cryptographic verification algorithms, the server confirms that the signature is valid for the transaction data and could only have been created by the holder of the corresponding private key, without ever needing access to the private key itself.

### What is the backend infrastructure for Palma Wallet?
Palma Wallet uses AWS (Amazon Web Services) for its backend infrastructure. User data is stored in DynamoDB tables, with the region set to us-east-1 (Cape Town). The architecture includes serverless components with Lambda functions handling transaction processing and user data management. User private keys are never stored on the server - only public keys are stored to verify transaction signatures.

### How does key generation work in Palma Wallet?
Key generation in Palma Wallet has evolved with different versions: 1) Initial version used RSA cryptography with fallback mechanisms if RSA wasn't available, 2) Latest version uses FIO Protocol for key generation, where random bytes are generated as a seed, then processed through cryptographic functions to create a private key, from which a public key is derived. This approach ensures secure, collision-resistant key pairs unique to each user.

## Upcoming Features

### What new cryptocurrencies will be added to Palma Wallet?
Palma Wallet plans to expand support beyond USDT to include major cryptocurrencies such as Bitcoin (BTC), Ethereum (ETH), and various stablecoins (USDC, DAI). The roadmap also includes support for popular tokens on both Ethereum and TRON networks.

### Will Palma Wallet support hardware wallets?
Yes, Palma Wallet is planning to add support for popular hardware wallets like Ledger and Trezor in a future update. This will allow users to connect their hardware wallets for additional security while still enjoying the user-friendly interface of Palma Wallet.

### Is there a plan to add DeFi features to Palma Wallet?
Yes, Palma Wallet has plans to introduce DeFi (Decentralized Finance) features in future updates. These will include staking, yield farming, and integration with popular DeFi protocols, allowing users to earn passive income on their crypto holdings directly from the wallet.

### Will Palma Wallet support NFTs?
Yes, support for viewing and managing NFTs (Non-Fungible Tokens) is on the Palma Wallet roadmap. This feature will allow users to view their NFT collections, receive NFTs, and eventually trade them directly within the app.

