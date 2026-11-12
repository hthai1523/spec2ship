const express = require('express');
const router = express.Router();
router.get('/api/customers', async (req, res) => { res.json([]); });
router.get('/api/customers/:id', async (req, res) => { res.json({}); });
module.exports = router;
