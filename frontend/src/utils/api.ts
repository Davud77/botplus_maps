// src/utils/api.ts
const API_URL = 'http://localhost:5080';

interface LoginResponse {
  status: string;
  message?: string;
}

export const login = async (username: string, password: string): Promise<LoginResponse> => {
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

export const fetchPanoramas = async (): Promise<any> => {
  const response = await fetch(`${API_URL}/panoramas`);
  return response.json();
};

export const uploadFiles = async (formData: FormData): Promise<any> => {
  const response = await fetch(`${API_URL}/upload`, {
    method: 'POST',
    body: formData,
  });

  return response.json();
};