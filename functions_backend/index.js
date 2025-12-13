const functions = require("firebase-functions");
const admin = require("firebase-admin");
const stripe = require("stripe")(process.env.STRIPE_SECRET_KEY);

admin.initializeApp();

// Crear sesión de pago de Stripe
exports.createCheckoutSession = functions.https.onCall(async (data, context) => {
  try {
    const session = await stripe.checkout.sessions.create({
      mode: "payment",
      payment_method_types: ["card"],
      line_items: [{
        price: process.env.PRICE_ID,
        quantity: 1,
      }],
      success_url: process.env.SUCCESS_URL,
      cancel_url: process.env.CANCEL_URL,
    });

    return { url: session.url };
  } catch (error) {
    console.error("Error creating checkout session:", error);
    throw new functions.https.HttpsError("internal", error.message);
  }
});
