import axios from 'axios'

const http = axios.create({ baseURL: '/api/v1' })

export const searchSimilar = (body) => http.post('/search/similar', body).then(r => r.data)
export const searchCitations = (body) => http.post('/search/citations', body).then(r => r.data)
export const searchPrecedents = (body) => http.post('/search/precedents', body).then(r => r.data)
export const analyzeArgument = (body) => http.post('/strategy/analyze', body).then(r => r.data)
export const getJudges = () => http.get('/search/judges').then(r => r.data)
export const getJudge = (name, caseType) =>
  http.get(`/search/judges/${encodeURIComponent(name)}`, { params: caseType ? { case_type: caseType } : {} }).then(r => r.data)
