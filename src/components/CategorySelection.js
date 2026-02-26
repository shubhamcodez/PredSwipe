import React, { useState, useEffect } from 'react';
import './CategorySelection.css';

const categories = [
  {
    id: 'football',
    name: 'Football',
    description: 'Premier League, Champions League & more',
    icon: '⚽'
  },
  {
    id: 'basketball',
    name: 'Basketball',
    description: 'NBA, EuroLeague & college games',
    icon: '🏀'
  },
  {
    id: 'tennis',
    name: 'Tennis',
    description: 'Grand Slams & ATP/WTA tours',
    icon: '🎾'
  },
  {
    id: 'crypto',
    name: 'Crypto',
    description: 'Bitcoin, Ethereum & altcoins',
    icon: '₿'
  },
  {
    id: 'stocks',
    name: 'Stocks',
    description: 'Tech, finance & market trends',
    icon: '📈'
  },
  {
    id: 'random',
    name: 'Random',
    description: 'Mix of all categories',
    icon: '🎲'
  }
];

const CategorySelection = ({ onCategorySelect, onBack, user }) => {
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [accountBalance, setAccountBalance] = useState(null);
  const [balanceLoading, setBalanceLoading] = useState(true);
  const [balanceError, setBalanceError] = useState(null);

  useEffect(() => {
    // Fetch balance from backend API
    const fetchBalance = async () => {
      if (!user?.kalshiApiKey || !user?.kalshiPrivateKey) {
        setBalanceLoading(false);
        return;
      }

      try {
        setBalanceLoading(true);
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
        // Handle different possible response formats
        let balance = null;
        if (data.balance !== undefined) {
          // If balance is in cents, convert to dollars
          balance = typeof data.balance === 'number' ? data.balance / 100 : parseFloat(data.balance) / 100;
        } else if (data.balance_cents !== undefined) {
          balance = parseFloat(data.balance_cents) / 100;
        } else if (data.account_balance !== undefined) {
          balance = parseFloat(data.account_balance);
        } else if (data.portfolio_balance !== undefined) {
          balance = parseFloat(data.portfolio_balance);
        } else {
          // Try to find any numeric field that might be balance
          const numericFields = Object.values(data).filter(v => typeof v === 'number' && v > 0);
          if (numericFields.length > 0) {
            balance = numericFields[0] / 100; // Assume cents if > 0
          }
        }
        
        if (balance !== null && !isNaN(balance)) {
          setAccountBalance(balance);
          setBalanceError(null);
        } else {
          throw new Error('Unable to parse balance from response');
        }
      } catch (error) {
        console.error('Error fetching balance:', error);
        setBalanceError(error.message);
      } finally {
        setBalanceLoading(false);
      }
    };

    fetchBalance();
  }, [user]);

  const handleCategoryClick = (category) => {
    // Immediately navigate to questions when category is clicked
    onCategorySelect(category);
  };

  const handleContinue = () => {
    if (selectedCategory) {
      onCategorySelect(selectedCategory);
    }
  };

  return (
    <div className="container">
      <div className="header">
        <div className="header-left">
          <div className="user-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
              <circle cx="12" cy="7" r="4"/>
            </svg>
          </div>
          <div className="user-info">
            <div className="user-name">Guest User</div>
            <div className="user-status">Active</div>
          </div>
        </div>
        
        <div className="header-right">
          <div className="balance-display">
            {balanceLoading ? (
              <div className="balance-amount">Loading...</div>
            ) : balanceError ? (
              <div className="balance-amount" style={{ color: '#ff6b6b' }}>Error</div>
            ) : accountBalance !== null ? (
              <div className="balance-amount">${accountBalance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
            ) : (
              <div className="balance-amount">--</div>
            )}
            <div className="balance-label">Balance</div>
          </div>
        </div>
      </div>
      
      <h1 className="title">Choose Your Category</h1>
      <p className="subtitle">Click on any category to start swiping predictions</p>
      
      <div className="category-grid">
        {categories.filter(category => category.id === 'basketball').map((category) => (
          <div
            key={category.id}
            className={`category-card ${selectedCategory?.id === category.id ? 'selected' : ''}`}
            onClick={() => handleCategoryClick(category)}
          >
            <div className="category-icon">{category.icon}</div>
            <h3>{category.name}</h3>
            <p>{category.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
};

export default CategorySelection;
