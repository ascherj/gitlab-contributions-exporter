import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

const LandingPage = () => {
  const [isLogin, setIsLogin] = useState(true);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    let endpoint = isLogin ? '/token' : '/signup';
    endpoint = 'http://localhost:8000' + endpoint;

    const loginFormData = new URLSearchParams();
    loginFormData.append('username', username);
    loginFormData.append('password', password);

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': isLogin ? 'application/x-www-form-urlencoded' : 'application/json', // Use the appropriate content type based on the login state
      },
      body: isLogin ? loginFormData : JSON.stringify({ username, password }), // Use the appropriate body based on the login state
    });

    if (response.ok) {
      const data = await response.json();
      localStorage.setItem('token', data.access_token);
      navigate('/welcome');
    } else {
      alert('Error: ' + (await response.text()));
    }
  };

  return (
    <div>
      <h1>GitLab Contributions Exporter</h1>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <button type="submit">{isLogin ? 'Login' : 'Sign Up'}</button>
      </form>
      <button onClick={() => setIsLogin(!isLogin)}>
        {isLogin ? 'Switch to Sign Up' : 'Switch to Login'}
      </button>
    </div>
  );
};

export default LandingPage;
