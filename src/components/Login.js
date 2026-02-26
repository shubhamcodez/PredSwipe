import React, { useState, useEffect } from 'react';
import './Login.css';

const Login = ({ onLogin }) => {
  const [kalshiApiKey, setKalshiApiKey] = useState('');
  const [kalshiPrivateKey, setKalshiPrivateKey] = useState('');

  useEffect(() => {
    // Load keys from sessionStorage if they exist
    const savedApiKey = sessionStorage.getItem('kalshiApiKey');
    const savedPrivateKey = sessionStorage.getItem('kalshiPrivateKey');
    
    if (savedApiKey && savedPrivateKey) {
      setKalshiApiKey(savedApiKey);
      setKalshiPrivateKey(savedPrivateKey);
    }
  }, []);

  useEffect(() => {
    // Store keys in sessionStorage whenever they change
    if (kalshiApiKey) {
      sessionStorage.setItem('kalshiApiKey', kalshiApiKey);
    }
    if (kalshiPrivateKey) {
      sessionStorage.setItem('kalshiPrivateKey', kalshiPrivateKey);
    }
  }, [kalshiApiKey, kalshiPrivateKey]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (kalshiApiKey.trim() && kalshiPrivateKey.trim()) {
      // Store keys in sessionStorage
      sessionStorage.setItem('kalshiApiKey', kalshiApiKey.trim());
      sessionStorage.setItem('kalshiPrivateKey', kalshiPrivateKey.trim());
      
      onLogin({ 
        username: 'User',
        email: 'user@predswipe.com',
        kalshiApiKey: kalshiApiKey.trim(),
        kalshiPrivateKey: kalshiPrivateKey.trim()
      });
    }
  };

  return (
    <div className="login-container">
      <div className="card login-form">
        <div className="logo">PredSwipe</div>
        <p className="tagline">Swipe your way through predictions</p>
        
        <form onSubmit={handleSubmit}>
          <div className="input-group">
            <label htmlFor="kalshiApiKey">Kalshi API Key</label>
            <input
              type="text"
              id="kalshiApiKey"
              value={kalshiApiKey}
              onChange={(e) => setKalshiApiKey(e.target.value)}
              placeholder="Enter your Kalshi API Key"
              required
            />
          </div>
          
          <div className="input-group">
            <label htmlFor="kalshiPrivateKey">Kalshi Private Key</label>
            <input
              type="text"
              id="kalshiPrivateKey"
              value={kalshiPrivateKey}
              onChange={(e) => setKalshiPrivateKey(e.target.value)}
              placeholder="Enter your Kalshi Private Key"
              required
            />
          </div>
          
          <button type="submit" className="btn" style={{ width: '100%' }}>
            Start Swiping
          </button>
        </form>
      </div>
    </div>
  );
};

export default Login;
