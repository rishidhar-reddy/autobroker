import { useEffect, useState } from 'react'
import { fetchProducts } from './api.js'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

const MOCK = {
  default: 'PROD-1001',
  products: [
    {
      product_id: 'PROD-1001',
      name: 'Industrial Widget',
      description: 'Heavy-duty steel widget, grade A',
      unit: 'pcs',
      vendor_company: 'Acme Supplies Co.',
      buyer_company: 'BuildCorp Ltd.',
      stock_quantity: 500,
      desired_quantity: 200,
      vendor_floor_price: 8,
      buyer_ceiling_price: 10,
      has_overlap: true,
    },
  ],
}

export function useProducts() {
  const [products, setProducts] = useState([])
  const [defaultId, setDefaultId] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    const load = USE_MOCK ? () => Promise.resolve(MOCK) : fetchProducts
    load()
      .then((data) => {
        setProducts(data.products ?? [])
        setDefaultId(data.default ?? data.products?.[0]?.product_id ?? null)
      })
      .catch((err) => setError(err.message))
  }, [])

  return { products, defaultId, error }
}
