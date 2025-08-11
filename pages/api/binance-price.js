import { binanceClient } from '../../lib/exchange';

export default async function handler(req, res) {
  try {
    const price = await binanceClient.prices({ symbol: 'BTCUSDT' });
    res.status(200).json(price);
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: 'Ошибка получения цены' });
  }
}
