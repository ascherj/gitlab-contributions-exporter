import React from 'react';

const Login = () => {
  const handleLogin = () => {
    window.location.href = 'http://localhost:8000/login';
  };

  return (
    <div>
      <h1>GitLab Contributions Exporter</h1>
      <button onClick={handleLogin}>Login with GitLab</button>
    </div>
  );
};

export default Login;
