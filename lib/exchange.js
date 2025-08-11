import Binance from 'binance-api-node';
import { RestClientV5 } from 'bybit-api';

const mode = process.env.TRADING_MODE || 'test';
const isTest = mode === 'test';

// Binance
export const binanceClient = Binance({
  apiKey: process.env.BINANCE_API_KEY,
  apiSecret: process.env.BINANCE_API_SECRET,
  test: isTest
});

// Bybit
export const bybitClient = new RestClientV5({
  key: process.env.BYBIT_API_KEY,
  secret: process.env.BYBIT_API_SECRET,
  testnet: isTest
});
