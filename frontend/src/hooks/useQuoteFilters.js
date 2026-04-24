import { useState, useCallback } from 'react';

/**
 * Hook que centraliza los 6 filtros rápidos de la pantalla Cotizaciones
 * y un helper para limpiarlos todos.
 */
export function useQuoteFilters() {
  const [filterClient, setFilterClient] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [filterSegment, setFilterSegment] = useState('');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');

  const clearFilters = useCallback(() => {
    setFilterClient('');
    setFilterStatus('');
    setFilterCategory('');
    setFilterSegment('');
    setFilterDateFrom('');
    setFilterDateTo('');
  }, []);

  return {
    filterClient, setFilterClient,
    filterStatus, setFilterStatus,
    filterCategory, setFilterCategory,
    filterSegment, setFilterSegment,
    filterDateFrom, setFilterDateFrom,
    filterDateTo, setFilterDateTo,
    clearFilters,
  };
}
