# English
echo "Testing English..."
curl -X POST https://chat-api.palmawallet.com/chat \
  -H "Content-Type: application/json" \
  -H "x-api-key: 3GPb6fumJ62NjYGJ1HaoG6hGbCVNfw866gThJ1cc" \
  -d '{
    "query": "How do I send cryptocurrency?"
  }'
echo -e "\n"

# Spanish - ✓ Already working
echo "Testing Spanish..."
curl -X POST https://chat-api.palmawallet.com/chat \
  -H "Content-Type: application/json" \
  -H "x-api-key: 3GPb6fumJ62NjYGJ1HaoG6hGbCVNfw866gThJ1cc" \
  -d '{
    "query": "¿Qué criptomonedas soporta Palma?"
  }'
echo -e "\n"

# French
echo "Testing French..."
curl -X POST https://chat-api.palmawallet.com/chat \
  -H "Content-Type: application/json" \
  -H "x-api-key: 3GPb6fumJ62NjYGJ1HaoG6hGbCVNfw866gThJ1cc" \
  -d '{
    "query": "Comment envoyer des cryptomonnaies?"
  }'
echo -e "\n"

# Portuguese
echo "Testing Portuguese..."
curl -X POST https://chat-api.palmawallet.com/chat \
  -H "Content-Type: application/json" \
  -H "x-api-key: 3GPb6fumJ62NjYGJ1HaoG6hGbCVNfw866gThJ1cc" \
  -d '{
    "query": "Como envio criptomoedas?"
  }'
echo -e "\n"

# Russian
echo "Testing Russian..."
curl -X POST https://chat-api.palmawallet.com/chat \
  -H "Content-Type: application/json" \
  -H "x-api-key: 3GPb6fumJ62NjYGJ1HaoG6hGbCVNfw866gThJ1cc" \
  -d '{
    "query": "Как отправить криптовалюту?"
  }'
echo -e "\n"

# German
echo "Testing German..."
curl -X POST https://chat-api.palmawallet.com/chat \
  -H "Content-Type: application/json" \
  -H "x-api-key: 3GPb6fumJ62NjYGJ1HaoG6hGbCVNfw866gThJ1cc" \
  -d '{
    "query": "Wie sende ich Kryptowährung?"
  }'
echo -e "\n"

# Nigerian Pidgin
echo "Testing Nigerian Pidgin..."
curl -X POST https://chat-api.palmawallet.com/chat \
  -H "Content-Type: application/json" \
  -H "x-api-key: 3GPb6fumJ62NjYGJ1HaoG6hGbCVNfw866gThJ1cc" \
  -d '{
    "query": "How I go send cryptocurrency?"
  }'
echo -e "\n"

# Yoruba
echo "Testing Yoruba..."
curl -X POST https://chat-api.palmawallet.com/chat \
  -H "Content-Type: application/json" \
  -H "x-api-key: 3GPb6fumJ62NjYGJ1HaoG6hGbCVNfw866gThJ1cc" \
  -d '{
    "query": "Bawo ni mo ṣe le fi owo crypto ranṣẹ?"
  }'
echo -e "\n"

# Hausa  
echo "Testing Hausa..."
curl -X POST https://chat-api.palmawallet.com/chat \
  -H "Content-Type: application/json" \
  -H "x-api-key: 3GPb6fumJ62NjYGJ1HaoG6hGbCVNfw866gThJ1cc" \
  -d '{
    "query": "Ta yaya zan aika cryptocurrency?"
  }'
echo -e "\n"

# Igbo
echo "Testing Igbo..."
curl -X POST https://chat-api.palmawallet.com/chat \
  -H "Content-Type: application/json" \
  -H "x-api-key: 3GPb6fumJ62NjYGJ1HaoG6hGbCVNfw866gThJ1cc" \
  -d '{
    "query": "Kedu ka m ga-esi ziga cryptocurrency?"
  }'
echo -e "\n"

# Swahili
echo "Testing Swahili..."
curl -X POST https://chat-api.palmawallet.com/chat \
  -H "Content-Type: application/json" \
  -H "x-api-key: 3GPb6fumJ62NjYGJ1HaoG6hGbCVNfw866gThJ1cc" \
  -d '{
    "query": "Jinsi ya kutuma cryptocurrency?"
  }'
echo -e "\n"

# Test AI response for a question not in FAQ
echo "Testing AI-generated response..."
curl -X POST https://chat-api.palmawallet.com/chat \
  -H "Content-Type: application/json" \
  -H "x-api-key: 3GPb6fumJ62NjYGJ1HaoG6hGbCVNfw866gThJ1cc" \
  -d '{
    "query": "Can I use Palma Wallet on multiple devices at the same time?"
  }'

