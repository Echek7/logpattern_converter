// functions/index.js (ACTUALIZADO)
// Consolidado y corregido para LogPattern Converter
// - licenseVerifier (HTTP POST)
// - logProcessorAI (onCall placeholder)
// - stripeWebhook (webhook handler for Stripe Checkout)
// - createCheckoutSession (crea sesiones de Checkout y devuelve URL)

// ====================================================================
// SETUP INICIAL
// ====================================================================

const functions = require("firebase-functions");
const admin = require("firebase-admin");

// Evitar inicializar más de una vez (hot reload / emulador)
if (!admin.apps.length) {
  admin.initializeApp();
}
const db = admin.firestore();

// ====================================================================
// UTIL: carga de configuración robusta (env vars, functions.config() fallback)
// ====================================================================
function loadConfig() {
  const cfg = {};
  // 1) from environment variables (preferred)
  cfg.STRIPE_SECRET_KEY = process.env.STRIPE_SECRET_KEY || process.env.STRIPE_SECRET || process.env.STRIPE_KEY || null;
  cfg.STRIPE_WEBHOOK_SECRET = process.env.STRIPE_WEBHOOK_SECRET || process.env.STRIPE_WEBHOOK || null;
  cfg.SENDGRID_API_KEY = process.env.SENDGRID_API_KEY || process.env.SENDGRID_KEY || null;
  cfg.EMAIL_FROM = process.env.EMAIL_FROM || process.env.SENDGRID_FROM || null;
  cfg.PRICE_ID = process.env.PRICE_ID || null;

  // 2) fallback to functions.config (legacy; you set via functions:config:set)
  try {
    const fn = functions && functions.config && functions.config();
    if (fn) {
      cfg.STRIPE_SECRET_KEY = cfg.STRIPE_SECRET_KEY || (fn.stripe && (fn.stripe.secret_key || fn.stripe.key));
      cfg.STRIPE_WEBHOOK_SECRET = cfg.STRIPE_WEBHOOK_SECRET || (fn.stripe && fn.stripe.webhook_secret);
      cfg.SENDGRID_API_KEY = cfg.SENDGRID_API_KEY || (fn.sendgrid && (fn.sendgrid.key || fn.sendgrid_api_key));
      cfg.EMAIL_FROM = cfg.EMAIL_FROM || (fn.sendgrid && (fn.sendgrid.from || fn.sendgrid_from));
      cfg.PRICE_ID = cfg.PRICE_ID || (fn.stripe && fn.stripe.price_id);
    }
  } catch (e) {
    console.warn('functions.config() not available or failed to load:', e && e.message);
  }

  return cfg;
}

const CFG = loadConfig();

// ====================================================================
// Paquetes externos que pueden fallar en entornos limitados
// ====================================================================
let stripeLib = null;
let stripe = null;
try {
  stripeLib = require('stripe');
  if (CFG.STRIPE_SECRET_KEY) {
    stripe = stripeLib(CFG.STRIPE_SECRET_KEY);
  }
} catch (e) {
  console.warn('Stripe package missing or failed to load:', e && e.message);
}

let sgMail = null;
try {
  sgMail = require('@sendgrid/mail');
  if (CFG.SENDGRID_API_KEY) {
    sgMail.setApiKey(CFG.SENDGRID_API_KEY);
    console.log('SendGrid initialized from config.');
  }
} catch (e) {
  console.warn('SendGrid package missing or failed to load:', e && e.message);
}

const { v4: uuidv4 } = require('uuid');
const crypto = require('crypto');

// ====================================================================
// LICENSE VERIFIER (HTTP - accepts POST JSON { license_key, machineId })
// ====================================================================
exports.licenseVerifier = functions.https.onRequest(async (req, res) => {
  try {
    // CORS preflight
    res.set('Access-Control-Allow-Origin', '*');
    if (req.method === 'OPTIONS') {
      res.set('Access-Control-Allow-Methods', 'POST, OPTIONS');
      res.set('Access-Control-Allow-Headers', 'Content-Type, Authorization');
      return res.status(204).send('');
    }

    if (req.method !== 'POST') {
      return res.status(405).json({ success: false, message: 'Método no permitido. Use POST.' });
    }

    const body = req.body || {};
    const license_key = body.license_key || body.licenseKey || null;
    const machineId = body.machineId || body.machine_id || null;

    functions.logger.info('Iniciando Verificación de Licencia CRC:', { license_key, machineId });

    if (!license_key || !machineId) {
      return res.status(400).json({
        success: false,
        message: 'Faltan la clave de licencia ("license_key") o el ID de la máquina ("machineId").'
      });
    }

    const licenseRef = db.collection('licenses').doc(String(license_key));

    const licenseDoc = await licenseRef.get();
    if (!licenseDoc.exists) {
      functions.logger.warn('Clave no encontrada', { license_key });
      return res.status(403).json({ success: false, message: 'CLAVE INVÁLIDA. La clave de licencia no fue encontrada.' });
    }

    const licenseData = licenseDoc.data() || {};

    if (licenseData.activated === true && licenseData.machineId && licenseData.machineId !== machineId) {
      functions.logger.warn('Clave ya en uso', { license_key, existingMachine: licenseData.machineId });
      return res.status(403).json({
        success: false,
        message: 'LICENCIA EN USO. Esta clave ya está activa en otra máquina. Contacte a soporte.'
      });
    }

    // Activar o confirmar la licencia para esta máquina
    await licenseRef.update({
      activated: true,
      activationDate: admin.firestore.FieldValue.serverTimestamp(),
      userId: licenseData.userId || 'anonymous_client',
      machineId: machineId
    });

    functions.logger.info('LICENCIA ACTIVADA/CONFIRMADA', { license_key, machineId });
    return res.status(200).json({
      success: true,
      message: `✅ LICENCIA ACTIVADA: Clave '${license_key}' registrada con éxito.`,
      licenseData: { key: license_key, machine: machineId, user: licenseData.userId || 'anonymous_client' }
    });

  } catch (err) {
    functions.logger.error('Error en licenseVerifier:', err);
    return res.status(500).json({ success: false, message: 'Error interno del servidor al procesar la licencia.' });
  }
});

// ====================================================================
// logProcessorAI (Callable) - placeholder para futura integración con IA
// ====================================================================
exports.logProcessorAI = functions.https.onCall(async (data, context) => {
  if (!context || !context.auth) {
    throw new functions.https.HttpsError('unauthenticated', 'Se requiere autenticación para procesar logs.');
  }

  const payloadPreview = data && data.logInput ? String(data.logInput).substring(0, 100) : null;
  return {
    success: true,
    message: 'Lógica de conversión de logs (placeholder).',
    processedData: payloadPreview ? `Processed preview: ${payloadPreview}...` : 'No log input provided.'
  };
});

// ====================================================================
// STRIPE WEBHOOK: stripeWebhook (HTTP)
// ====================================================================
exports.stripeWebhook = functions.https.onRequest(async (req, res) => {
  // Healthcheck
  if (req.method === 'GET') {
    return res.status(200).send('stripeWebhook ready');
  }

  let event = null;
  const sig = req.headers['stripe-signature'] || req.headers['Stripe-Signature'];

  try {
    if (CFG.STRIPE_WEBHOOK_SECRET && sig && stripe) {
      // rawBody should be available in Cloud Functions runtime; construct event safely
      const rawBody = req.rawBody;
      event = stripe.webhooks.constructEvent(rawBody, sig, CFG.STRIPE_WEBHOOK_SECRET);
    } else {
      // No signature configured: accept parsed body (ONLY for testing)
      event = req.body;
    }
  } catch (err) {
    console.error('Stripe webhook signature verification failed:', err);
    return res.status(400).send(`Webhook Error: ${err.message || err}`);
  }

  // Only process checkout.session.completed (and payment_intent.succeeded optionally)
  const eventType = event && event.type ? event.type : null;
  if (eventType && eventType !== 'checkout.session.completed' && eventType !== 'payment_intent.succeeded') {
    return res.status(200).send({ received: true });
  }

  const session = eventType ? event.data.object : event;
  const sessionId = session.id || session.session_id || `sess_${uuidv4()}`;

  try {
    // Idempotency: check stripe_sessions
    const sessionRef = db.collection('stripe_sessions').doc(sessionId);
    const sessionDoc = await sessionRef.get();
    if (sessionDoc.exists) {
      console.log('Stripe session already processed:', sessionId);
      return res.status(200).send({ processed: true, note: 'already processed' });
    }

    // Payment status check (best effort)
    const paymentStatus = session.payment_status || (session.payment_intent && session.payment_intent.status) || session.status || 'unknown';
    if (paymentStatus !== 'paid' && paymentStatus !== 'succeeded' && paymentStatus !== 'complete') {
      console.warn('Payment status not "paid"/"succeeded":', paymentStatus, ' — continuing but verify in production.');
    }

    // Generate license key (secure)
    const raw = crypto.randomBytes(32).toString('hex'); // 64 hex chars
    const licenseKey = `LP-${raw}`;

    const plan = (session.metadata && session.metadata.plan) ? session.metadata.plan : 'Standard';

    const licenseDoc = {
      activated: false,
      plan: plan,
      machineId: "",
      userId: "",
      stripeSessionId: sessionId,
      creationDate: admin.firestore.FieldValue.serverTimestamp()
    };

    // Save license
    await db.collection('licenses').doc(licenseKey).set(licenseDoc, { merge: false });

    // Mark session processed
    await sessionRef.set({
      processed: true,
      licenseKey: licenseKey,
      createdAt: admin.firestore.FieldValue.serverTimestamp(),
      rawSession: session
    });

    console.log('License generated:', licenseKey, 'for session', sessionId);

    // Send email if possible
    const customerEmail = (session.customer_details && session.customer_details.email)
      ? session.customer_details.email
      : (session.customer_email || (session.metadata && session.metadata.email));

    if (customerEmail && CFG.SENDGRID_API_KEY && CFG.EMAIL_FROM) {
      const msg = {
        to: customerEmail,
        from: CFG.EMAIL_FROM,
        subject: 'Tu licencia de LogPattern Converter',
        text: `Gracias por tu compra.\n\nTu clave de activación: ${licenseKey}\n\nInstrucciones:\n1) Instala: pip install logpattern_converter\n2) Activa: logconv activar ${licenseKey}\n\nSi tienes problemas, abre un issue en GitHub.`,
        html: `<p>Gracias por tu compra.</p><p><strong>Tu clave de activación:</strong> <code>${licenseKey}</code></p><p>Instrucciones:<br>1) Instala: <code>pip install logpattern_converter</code><br>2) Activa: <code>logconv activar ${licenseKey}</code></p>`
      };

      try {
        await sgMail.send(msg);
        console.log('Email enviado a', customerEmail);
        await sessionRef.update({ emailSent: true });
      } catch (emailErr) {
        console.error('Error enviando email con SendGrid:', emailErr);
        await sessionRef.update({ emailSent: false, emailError: String(emailErr) });
      }
    } else {
      console.log('No email sent: missing customerEmail or SendGrid config.');
    }

    return res.status(200).send({ success: true, licenseKey: licenseKey });
  } catch (error) {
    console.error('Error processing stripe webhook:', error);
    return res.status(500).send({ error: String(error) });
  }
});

// ====================================================================
// CREATE CHECKOUT SESSION - endpoint para crear sesiones de Stripe Checkout
// ====================================================================
exports.createCheckoutSession = functions.https.onRequest(async (req, res) => {
  try {
    // CORS básico
    res.set('Access-Control-Allow-Origin', '*');
    if (req.method === 'OPTIONS') {
      res.set('Access-Control-Allow-Methods', 'POST, OPTIONS');
      res.set('Access-Control-Allow-Headers', 'Content-Type');
      return res.status(204).send('');
    }
    if (req.method !== 'POST') {
      return res.status(405).json({ error: 'Use POST' });
    }

    if (!stripe) {
      return res.status(500).json({ error: 'Stripe not configured' });
    }

    const body = req.body || {};
    const priceId = body.priceId;
    const customer_email = body.customer_email || null;
    const success_url = body.success_url || `${req.protocol}://${req.get('host')}/success.html`;
    const cancel_url = body.cancel_url || `${req.protocol}://${req.get('host')}/cancel.html`;

    if (!priceId) {
      return res.status(400).json({ error: 'priceId required' });
    }

    // Create Checkout Session
    const session = await stripe.checkout.sessions.create({
      mode: 'payment',
      payment_method_types: ['card'],
      line_items: [
        { price: priceId, quantity: 1 }
      ],
      success_url: success_url + '?session_id={CHECKOUT_SESSION_ID}',
      cancel_url: cancel_url,
      customer_email: customer_email,
      metadata: {
        plan: 'Standard'
      }
    });

    return res.status(200).json({ url: session.url, id: session.id });
  } catch (err) {
    console.error('createCheckoutSession error:', err);
    return res.status(500).json({ error: String(err) });
  }
});
