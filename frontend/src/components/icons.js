import L from 'leaflet';

const defaultIcon = new L.Icon({
  iconUrl: '/images/default-icon.png',
  iconSize: [18, 18],
  iconAnchor: [9, 9]
});

const activeIcon = new L.Icon({
  iconUrl: '/images/active-icon.png',
  iconSize: [20, 20],
  iconAnchor: [10, 10]
});

export { defaultIcon, activeIcon };
