import axios from 'axios';
import CryptoJS from 'crypto-js';

// -------------------------------
// 1️⃣ SHA-256 哈希密码
// -------------------------------
function hashPassword(password: string): string {
  return CryptoJS.SHA256(password).toString(CryptoJS.enc.Hex);
}

// -------------------------------
// 2️⃣ HMAC-SHA256 签名
// -------------------------------
function sign(apiKey: string, message: string): string {
  return CryptoJS.HmacSHA256(message, apiKey).toString(CryptoJS.enc.Hex);
}

// -------------------------------
// 3️⃣ Axios 客户端
// -------------------------------
function getClient(remoteAddress: string, password: string) {
  const client = axios.create({
    baseURL: remoteAddress,
    timeout: 5000,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  client.interceptors.request.use((config) => {
    const timestamp = Date.now().toString();
    const method = (config.method || 'GET').toUpperCase();

    // ✅ 只取 path，保证和后端一致
    const urlObj = new URL(config.url!, config.baseURL);
    const path = urlObj.pathname;

    // ✅ 规范化 body
    let body = '';
    if (config.data !== undefined) {
      body = JSON.stringify(config.data);
    }

    const hashedPassword = hashPassword(password);
    const message = `${timestamp}${method}${path}${body}`;
    const signature = sign(hashedPassword, message);

    config.headers['X-Server-Pwd'] = hashedPassword;
    config.headers['X-Timestamp'] = timestamp;
    config.headers['X-Signature'] = signature;

    return config;
  });

  return client;
}

export default getClient;