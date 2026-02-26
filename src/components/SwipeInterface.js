import React, { useState, useEffect, useRef } from 'react';
import './SwipeInterface.css';

// Sample prediction data with prices
const predictionData = {
  football: [
    { question: "Will Manchester United win their next game?", price: 0.45 },
    { question: "Will Liverpool score more than 2 goals?", price: 0.35 },
    { question: "Will Arsenal finish in the top 4?", price: 0.65 },
    { question: "Will Chelsea win the Champions League?", price: 0.15 },
    { question: "Will Manchester City win the Premier League?", price: 0.75 },
    { question: "Will Tottenham beat their next opponent?", price: 0.55 },
    { question: "Will Newcastle finish in the top 6?", price: 0.25 },
    { question: "Will Brighton score in their next match?", price: 0.60 }
  ],
  basketball: [
    { question: "Will the Lakers win their next game?", price: 0.55 },
    { question: "Will LeBron score more than 25 points?", price: 0.50 },
    { question: "Will the Warriors make the playoffs?", price: 0.35 },
    { question: "Will the Celtics win the Eastern Conference?", price: 0.25 },
    { question: "Will the Nuggets repeat as champions?", price: 0.15 },
    { question: "Will Luka Doncic score 30+ points?", price: 0.60 },
    { question: "Will the Heat make the Finals?", price: 0.20 },
    { question: "Will the Bucks win 50+ games?", price: 0.70 }
  ],
  tennis: [
    { question: "Will Djokovic win the next Grand Slam?", price: 0.40 },
    { question: "Will Serena Williams return to top 10?", price: 0.05 },
    { question: "Will Nadal win the French Open?", price: 0.30 },
    { question: "Will Federer make a comeback?", price: 0.02 },
    { question: "Will Osaka win another major?", price: 0.20 },
    { question: "Will Medvedev win Wimbledon?", price: 0.35 },
    { question: "Will Halep return to form?", price: 0.12 },
    { question: "Will Thiem win a Grand Slam?", price: 0.08 }
  ],
  crypto: [
    { question: "Will Bitcoin reach $100,000?", price: 0.30 },
    { question: "Will Ethereum outperform Bitcoin?", price: 0.55 },
    { question: "Will Solana reach $200?", price: 0.20 },
    { question: "Will Cardano hit $5?", price: 0.05 },
    { question: "Will Dogecoin reach $1?", price: 0.01 },
    { question: "Will Polygon surge 50%?", price: 0.40 },
    { question: "Will Chainlink hit $50?", price: 0.12 },
    { question: "Will Avalanche reach $100?", price: 0.25 }
  ],
  stocks: [
    { question: "Will Apple stock reach $200?", price: 0.60 },
    { question: "Will Tesla stock surge 30%?", price: 0.35 },
    { question: "Will Amazon beat earnings?", price: 0.55 },
    { question: "Will Google stock hit $150?", price: 0.45 },
    { question: "Will Microsoft reach $400?", price: 0.65 },
    { question: "Will Netflix stock recover?", price: 0.30 },
    { question: "Will Meta stock bounce back?", price: 0.40 },
    { question: "Will Nvidia continue rising?", price: 0.50 }
  ],
  random: [
    { question: "Will Manchester United win their next game?", price: 0.45 },
    { question: "Will Bitcoin reach $100,000?", price: 0.30 },
    { question: "Will the Lakers win their next game?", price: 0.55 },
    { question: "Will Apple stock reach $200?", price: 0.60 },
    { question: "Will Djokovic win the next Grand Slam?", price: 0.40 },
    { question: "Will Tesla stock surge 30%?", price: 0.35 },
    { question: "Will Arsenal finish in the top 4?", price: 0.65 },
    { question: "Will Ethereum outperform Bitcoin?", price: 0.55 }
  ]
};

// Look for common team abbreviations - defined at component level
const teamMap = {
  'MIA': 'Miami',
  'SAS': 'San Antonio',
  'LAL': 'Lakers',
  'GSW': 'Warriors',
  'BOS': 'Celtics',
  'NYK': 'Knicks',
  'CHI': 'Bulls',
  'PHI': '76ers',
  'DAL': 'Mavericks',
  'DEN': 'Nuggets',
  'PHX': 'Suns',
  'MIL': 'Bucks',
  'BKN': 'Nets',
  'LAC': 'Clippers',
  'ATL': 'Hawks',
  'MEM': 'Grizzlies',
  'MIN': 'Timberwolves',
  'NOP': 'Pelicans',
  'OKC': 'Thunder',
  'POR': 'Trail Blazers',
  'SAC': 'Kings',
  'UTA': 'Jazz',
  'HOU': 'Rockets',
  'CHA': 'Hornets',
  'DET': 'Pistons',
  'IND': 'Pacers',
  'ORL': 'Magic',
  'TOR': 'Raptors',
  'WAS': 'Wizards',
  'CLE': 'Cavaliers'
};

const SwipeInterface = ({ category, onBack, user }) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [predictions, setPredictions] = useState([]);
  const [stats, setStats] = useState({ yes: 0, no: 0 });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [swipeDirection, setSwipeDirection] = useState(null);
  const [accountBalance, setAccountBalance] = useState(null);
  const [balanceLoading, setBalanceLoading] = useState(true);
  const cardRef = useRef(null);

  // Fetch balance
  useEffect(() => {
    const fetchBalance = async () => {
      if (!user?.kalshiApiKey || !user?.kalshiPrivateKey) {
        setBalanceLoading(false);
        return;
      }

      try {
        const response = await fetch('http://localhost:5000/api/balance', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            kalshiApiKey: user.kalshiApiKey,
            kalshiPrivateKey: user.kalshiPrivateKey
          })
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || 'Failed to fetch balance');
        }

        const data = await response.json();
        let balance = null;
        if (data.balance !== undefined) {
          balance = typeof data.balance === 'number' ? data.balance / 100 : parseFloat(data.balance) / 100;
        } else if (data.balance_cents !== undefined) {
          balance = parseFloat(data.balance_cents) / 100;
        }
        
        if (balance !== null && !isNaN(balance)) {
          setAccountBalance(balance);
        }
      } catch (err) {
        console.error('Error fetching balance:', err);
      } finally {
        setBalanceLoading(false);
      }
    };

    fetchBalance();
  }, [user]);

  useEffect(() => {
    // Fetch real markets from Kalshi API
    const fetchMarkets = async () => {
      if (!user?.kalshiApiKey || !user?.kalshiPrivateKey) {
        // Fallback to sample data if no API keys
        const categoryPredictions = predictionData[category.id] || predictionData.random;
        setPredictions(categoryPredictions);
        setIsLoading(false);
        return;
      }

      try {
        setIsLoading(true);
        setError(null);

        // Map category IDs to series tickers
        const seriesTickerMap = {
          'basketball': 'KXNBAGAME',
          'football': 'KXNFOOTBALL',
          'tennis': 'KXNTENNIS',
          'crypto': 'KXNCRYPTO',
          'stocks': 'KXNSTOCKS',
          'random': 'KXNBAGAME'
        };

        const seriesTicker = seriesTickerMap[category.id] || 'KXNBAGAME';

        const response = await fetch('http://localhost:5000/api/markets', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            kalshiApiKey: user.kalshiApiKey,
            kalshiPrivateKey: user.kalshiPrivateKey,
            series_ticker: seriesTicker,
            limit: 100
          })
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || 'Failed to fetch markets');
        }

        const data = await response.json();
        const markets = data.markets || [];
        
        // Convert markets to prediction format
        const formattedMarkets = markets.map(market => {
          // Parse ticker to extract team names
          // Format: KXNBAGAME-25OCT30MIASAS-SAS where SAS is the team that wins
          let question = market.title || market.ticker;
          let teamName = '';
          let matchInfo = '';
          
          if (market.ticker) {
            const tickerParts = market.ticker.split('-');
            if (tickerParts.length >= 3) {
              // Get the team abbreviation (last part after final hyphen)
              teamName = tickerParts[tickerParts.length - 1];
              
              // Try to extract match info from the middle parts
              // Format example: 25OCT30MIASAS -> Date + Teams
              if (tickerParts.length >= 2 && tickerParts[1]) {
                const matchString = tickerParts[1];
                
                // Find all teams in the match string
                const teamsInMatch = [];
                for (const [abbr, fullName] of Object.entries(teamMap)) {
                  if (matchString.includes(abbr)) {
                    teamsInMatch.push(fullName);
                  }
                }
                
                if (teamsInMatch.length >= 2) {
                  matchInfo = teamsInMatch.join(' vs ');
                } else if (teamMap[teamName]) {
                  matchInfo = `${teamMap[teamName]} Wins`;
                }
              }
              
              // Create a better question format
              if (matchInfo && teamName) {
                question = `${matchInfo} - Will ${teamMap[teamName] || teamName} Win?`;
              } else if (teamName) {
                question = `Will ${teamMap[teamName] || teamName} Win?`;
              }
            }
          }
          
          return {
            question: question,
            ticker: market.ticker,
            teamName: teamName,
            matchInfo: matchInfo,
            price: market.yes_bid ? parseFloat(market.yes_bid) / 100 : 0.5, // Convert cents to decimal
            yes_bid: market.yes_bid,
            no_bid: market.no_bid,
            yes_ask: market.yes_ask,
            no_ask: market.no_ask
          };
        });

        if (formattedMarkets.length > 0) {
          setPredictions(formattedMarkets);
        } else {
          // Fallback to sample data if no markets found
          const categoryPredictions = predictionData[category.id] || predictionData.random;
          setPredictions(categoryPredictions);
        }
      } catch (err) {
        console.error('Error fetching markets:', err);
        setError(err.message);
        // Fallback to sample data on error
        const categoryPredictions = predictionData[category.id] || predictionData.random;
        setPredictions(categoryPredictions);
      } finally {
        setIsLoading(false);
      }
    };

    fetchMarkets();
  }, [category, user]);

  useEffect(() => {
    const handleKeyPress = (e) => {
      if (currentIndex >= predictions.length) return;
      
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        handleSwipe('no');
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        handleSwipe('yes');
      } else if (e.key === ' ' || e.key === 'Space') {
        e.preventDefault();
        // Skip without placing order
        setCurrentIndex(prev => prev + 1);
        setSwipeDirection(null);
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [currentIndex, predictions.length]);

  const handleSwipe = async (direction) => {
    if (currentIndex >= predictions.length) return;

    setSwipeDirection(direction);
    setStats(prev => ({
      ...prev,
      [direction]: prev[direction] + 1
    }));

    // Place order on Kalshi
    const currentPrediction = predictions[currentIndex];
    if (currentPrediction?.ticker && user?.kalshiApiKey && user?.kalshiPrivateKey) {
      try {
        const response = await fetch('http://localhost:5000/api/place_order', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            kalshiApiKey: user.kalshiApiKey,
            kalshiPrivateKey: user.kalshiPrivateKey,
            ticker: currentPrediction.ticker,
            side: direction, // 'yes' or 'no'
            count: 1
          })
        });

        if (!response.ok) {
          const errorData = await response.json();
          console.error('Order failed:', errorData.error);
        } else {
          const data = await response.json();
          console.log('Order placed successfully:', data);
        }
      } catch (err) {
        console.error('Error placing order:', err);
      }
    }

    setTimeout(() => {
      setCurrentIndex(prev => prev + 1);
      setSwipeDirection(null);
    }, 300);
  };

  const resetSession = () => {
    setCurrentIndex(0);
    setStats({ yes: 0, no: 0 });
    setIsLoading(true);
    setTimeout(() => {
      setIsLoading(false);
    }, 500);
  };

  if (isLoading) {
    return (
      <div className="swipe-container">
        <div className="loading">
          <div className="spinner"></div>
          {error ? `Error: ${error}` : 'Loading markets from Kalshi...'}
        </div>
      </div>
    );
  }

  if (currentIndex >= predictions.length) {
    return (
      <div className="swipe-container">
        <button className="back-btn" onClick={onBack}>
          ←
        </button>
        
        <div className="empty-state">
          <h2>🎉 Session Complete!</h2>
          <p>You've swiped through all {category.name} predictions</p>
          
          <div className="stats">
            <div className="stat-item">
              <div className="stat-number">{stats.yes}</div>
              <div className="stat-label">Yes Votes</div>
            </div>
            <div className="stat-item">
              <div className="stat-number">{stats.no}</div>
              <div className="stat-label">No Votes</div>
            </div>
            <div className="stat-item">
              <div className="stat-number">{stats.yes + stats.no}</div>
              <div className="stat-label">Total</div>
            </div>
          </div>
          
          <button className="btn" onClick={resetSession}>
            Start New Session
          </button>
        </div>
      </div>
    );
  }

  const currentPrediction = predictions[currentIndex];
  const currentPrice = currentPrediction?.price || 1.0;

  return (
    <div className="swipe-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <button className="back-btn" onClick={onBack}>
          ←
        </button>

        <div className="account-balance">
          {balanceLoading ? (
            <div className="balance-amount">Loading...</div>
          ) : (accountBalance !== null && accountBalance !== undefined && !isNaN(accountBalance)) ? (
            <div className="balance-amount">${accountBalance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
          ) : (
            <div className="balance-amount">--</div>
          )}
          <div className="balance-label">Balance</div>
        </div>
      </div>

      <div className="prediction-card-container">
        <div 
          ref={cardRef}
          className={`prediction-card ${swipeDirection ? `swipe-${swipeDirection}` : ''}`}
        >
          <div className="prediction-header">
            <div className="prediction-category">{category.name}</div>
            <div className="prediction-price">{(currentPrice * 100).toFixed(0)}¢</div>
          </div>
          <div className="prediction-question">{currentPrediction?.question}</div>
          {currentPrediction?.ticker && (
            <div className="prediction-ticker" style={{ fontSize: '0.85rem', opacity: 0.7, marginTop: '10px' }}>
              Ticker: {currentPrediction.ticker}
            </div>
          )}
          
          <div className="swipe-indicators">
            <div className={`swipe-indicator no ${swipeDirection === 'no' ? 'show' : ''}`}>
              NO
            </div>
            <div className={`swipe-indicator yes ${swipeDirection === 'yes' ? 'show' : ''}`}>
              YES
            </div>
          </div>
        </div>
      </div>

      <div className="swipe-controls">
        <button 
          className="swipe-btn no"
          onClick={() => handleSwipe('no')}
        >
          ✕
        </button>
        <button 
          className="swipe-btn skip"
          onClick={() => {
            setCurrentIndex(prev => prev + 1);
            setSwipeDirection(null);
          }}
          style={{
            background: '#f0f0f0',
            color: '#666',
            fontSize: '1.2rem',
            border: '2px solid #ddd'
          }}
        >
          ↻
        </button>
        <button 
          className="swipe-btn yes"
          onClick={() => handleSwipe('yes')}
        >
          ✓
        </button>
      </div>

      <div className="keyboard-hint">
        Use ← (No), Space (Skip), or → (Yes) to navigate
      </div>
    </div>
  );
};

export default SwipeInterface;
