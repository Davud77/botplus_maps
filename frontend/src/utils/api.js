const API_URL = 'https://api.botplus.ru';

export const login = async (username, password) => {
  const response = await fetch(`${API_URL}/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ username, password })
  });

  if (!response.ok) {
    throw new Error('Ошибка сети');
  }

  return response.json();
};

export const fetchPanoramas = async () => {
  const response = await fetch(`${API_URL}/panoramas`);
  return response.json();
};

export const uploadFiles = async (formData) => {
  const response = await fetch(`${API_URL}/upload`, {
    method: 'POST',
    body: formData,
  });

  return response.json();
};
