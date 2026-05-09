---
name: push-notifications-patterns
description: "Master push notifications patterns with expert patterns and practices."
type: feature
---

# Push Notifications Patterns

> Patrones para notificaciones push en móvil y web.

---

## Descripción

Esta skill cubre implementación de push notifications usando Firebase Cloud Messaging (FCM), Apple Push Notification Service (APNs), y Web Push.

---

## Arquitectura

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Tu App    │────▶│  Tu Server  │────▶│  FCM/APNs   │
│  (Cliente)  │     │  (Backend)  │     │  (Provider) │
└─────────────┘     └─────────────┘     └─────────────┘
      │                                        │
      │         Push Notification              │
      ◀────────────────────────────────────────┘
```

---

## Firebase Cloud Messaging (FCM)

### Setup Server (Node.js)

```typescript
import admin from 'firebase-admin';

admin.initializeApp({
  credential: admin.credential.cert({
    projectId: process.env.FIREBASE_PROJECT_ID,
    clientEmail: process.env.FIREBASE_CLIENT_EMAIL,
    privateKey: process.env.FIREBASE_PRIVATE_KEY?.replace(/\\n/g, '\n'),
  }),
});

const messaging = admin.messaging();
```

### Enviar Notificación

```typescript
interface PushNotification {
  title: string;
  body: string;
  imageUrl?: string;
  data?: Record<string, string>;
}

// A un dispositivo
async function sendToDevice(token: string, notification: PushNotification) {
  const message: admin.messaging.Message = {
    token,
    notification: {
      title: notification.title,
      body: notification.body,
      imageUrl: notification.imageUrl,
    },
    data: notification.data,
    android: {
      priority: 'high',
      notification: {
        channelId: 'default',
        sound: 'default',
        clickAction: 'FLUTTER_NOTIFICATION_CLICK',
      },
    },
    apns: {
      payload: {
        aps: {
          alert: {
            title: notification.title,
            body: notification.body,
          },
          badge: 1,
          sound: 'default',
        },
      },
    },
  };

  try {
    const response = await messaging.send(message);
    console.log('Notification sent:', response);
    return { success: true, messageId: response };
  } catch (error: any) {
    console.error('Error sending notification:', error);

    // Manejar token inválido
    if (error.code === 'messaging/registration-token-not-registered') {
      await removeInvalidToken(token);
    }

    return { success: false, error: error.message };
  }
}

// A múltiples dispositivos
async function sendToMultiple(tokens: string[], notification: PushNotification) {
  const message: admin.messaging.MulticastMessage = {
    tokens,
    notification: {
      title: notification.title,
      body: notification.body,
    },
    data: notification.data,
  };

  const response = await messaging.sendEachForMulticast(message);

  // Procesar respuestas
  const invalidTokens: string[] = [];
  response.responses.forEach((resp, idx) => {
    if (!resp.success && resp.error?.code === 'messaging/registration-token-not-registered') {
      invalidTokens.push(tokens[idx]);
    }
  });

  // Limpiar tokens inválidos
  if (invalidTokens.length > 0) {
    await removeInvalidTokens(invalidTokens);
  }

  return {
    successCount: response.successCount,
    failureCount: response.failureCount,
    invalidTokens,
  };
}

// A un topic
async function sendToTopic(topic: string, notification: PushNotification) {
  const message: admin.messaging.Message = {
    topic,
    notification: {
      title: notification.title,
      body: notification.body,
    },
    data: notification.data,
  };

  return messaging.send(message);
}
```

### Gestión de Topics

```typescript
// Suscribir usuarios a un topic
async function subscribeToTopic(tokens: string[], topic: string) {
  const response = await messaging.subscribeToTopic(tokens, topic);
  return response;
}

// Desuscribir
async function unsubscribeFromTopic(tokens: string[], topic: string) {
  const response = await messaging.unsubscribeFromTopic(tokens, topic);
  return response;
}

// Casos de uso
await subscribeToTopic(userTokens, 'promotions');
await subscribeToTopic(userTokens, `user-${userId}`); // Topic por usuario
await subscribeToTopic(userTokens, `team-${teamId}`); // Topic por equipo
```

### Cliente React Native

```typescript
import messaging from '@react-native-firebase/messaging';
import { Platform } from 'react-native';

// Solicitar permisos
async function requestPermission() {
  const authStatus = await messaging().requestPermission();
  const enabled =
    authStatus === messaging.AuthorizationStatus.AUTHORIZED ||
    authStatus === messaging.AuthorizationStatus.PROVISIONAL;

  if (enabled) {
    console.log('Authorization status:', authStatus);
  }

  return enabled;
}

// Obtener token
async function getToken() {
  const token = await messaging().getToken();
  console.log('FCM Token:', token);

  // Enviar token al servidor
  await api.post('/users/device-token', { token, platform: Platform.OS });

  return token;
}

// Listener de token refresh
messaging().onTokenRefresh(async (token) => {
  await api.post('/users/device-token', { token, platform: Platform.OS });
});

// Listener de notificaciones en foreground
messaging().onMessage(async (remoteMessage) => {
  console.log('Foreground notification:', remoteMessage);
  // Mostrar notificación local o in-app
  showInAppNotification(remoteMessage);
});

// Listener cuando se abre desde notificación
messaging().onNotificationOpenedApp((remoteMessage) => {
  console.log('Notification opened app:', remoteMessage);
  navigateToScreen(remoteMessage.data);
});

// Check si la app se abrió desde notificación
messaging().getInitialNotification().then((remoteMessage) => {
  if (remoteMessage) {
    navigateToScreen(remoteMessage.data);
  }
});
```

---

## Web Push

### Setup con web-push

```typescript
import webpush from 'web-push';

webpush.setVapidDetails(
  'mailto:contact@yourapp.com',
  process.env.VAPID_PUBLIC_KEY!,
  process.env.VAPID_PRIVATE_KEY!
);

// Generar VAPID keys (una vez)
// const vapidKeys = webpush.generateVAPIDKeys();
```

### Enviar Web Push

```typescript
interface WebPushSubscription {
  endpoint: string;
  keys: {
    p256dh: string;
    auth: string;
  };
}

async function sendWebPush(subscription: WebPushSubscription, payload: object) {
  try {
    await webpush.sendNotification(
      subscription,
      JSON.stringify(payload),
      {
        TTL: 3600,
        urgency: 'normal',
      }
    );
    return { success: true };
  } catch (error: any) {
    if (error.statusCode === 410) {
      // Subscription expiró
      await removeSubscription(subscription.endpoint);
    }
    return { success: false, error: error.message };
  }
}
```

### Cliente Web (Service Worker)

```javascript
// sw.js - Service Worker
self.addEventListener('push', (event) => {
  const data = event.data?.json() || {};

  const options = {
    body: data.body,
    icon: '/icon-192.png',
    badge: '/badge.png',
    image: data.image,
    data: data.data,
    actions: data.actions || [],
    vibrate: [200, 100, 200],
    tag: data.tag || 'default',
    renotify: true,
  };

  event.waitUntil(
    self.registration.showNotification(data.title || 'Notification', options)
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  const url = event.notification.data?.url || '/';

  event.waitUntil(
    clients.matchAll({ type: 'window' }).then((clientList) => {
      // Si ya hay una ventana abierta, enfocarla
      for (const client of clientList) {
        if (client.url === url && 'focus' in client) {
          return client.focus();
        }
      }
      // Si no, abrir nueva ventana
      return clients.openWindow(url);
    })
  );
});
```

### Suscripción desde el Cliente

```typescript
async function subscribeToPush() {
  const registration = await navigator.serviceWorker.ready;

  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
  });

  // Enviar suscripción al servidor
  await api.post('/push/subscribe', {
    subscription: subscription.toJSON(),
  });

  return subscription;
}

function urlBase64ToUint8Array(base64String: string) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}
```

---

## Servicio de Notificaciones Unificado

```typescript
interface NotificationService {
  sendToUser(userId: string, notification: Notification): Promise<void>;
  sendToSegment(segment: string, notification: Notification): Promise<void>;
  sendScheduled(userId: string, notification: Notification, sendAt: Date): Promise<void>;
}

class UnifiedNotificationService implements NotificationService {
  constructor(
    private fcm: FirebaseMessaging,
    private webPush: WebPushService,
    private db: Database
  ) {}

  async sendToUser(userId: string, notification: Notification) {
    // Obtener todos los dispositivos del usuario
    const devices = await this.db.getUserDevices(userId);

    const results = await Promise.allSettled([
      // Mobile (FCM)
      ...devices
        .filter((d) => d.platform !== 'web')
        .map((d) => this.fcm.send(d.token, notification)),

      // Web Push
      ...devices
        .filter((d) => d.platform === 'web')
        .map((d) => this.webPush.send(d.subscription, notification)),
    ]);

    // Log resultados
    const failed = results.filter((r) => r.status === 'rejected');
    if (failed.length > 0) {
      console.error(`${failed.length} notifications failed for user ${userId}`);
    }
  }

  async sendToSegment(segment: string, notification: Notification) {
    // Usar FCM topics para mobile
    await this.fcm.sendToTopic(segment, notification);

    // Para web, obtener suscripciones del segmento
    const webSubscriptions = await this.db.getWebSubscriptionsBySegment(segment);
    await Promise.allSettled(
      webSubscriptions.map((sub) => this.webPush.send(sub, notification))
    );
  }

  async sendScheduled(userId: string, notification: Notification, sendAt: Date) {
    await this.queue.add('send-notification', {
      userId,
      notification,
    }, {
      delay: sendAt.getTime() - Date.now(),
    });
  }
}
```

---

## Preferencias de Usuario

```typescript
interface NotificationPreferences {
  userId: string;
  email: boolean;
  push: boolean;
  sms: boolean;
  categories: {
    marketing: boolean;
    transactional: boolean;
    social: boolean;
    updates: boolean;
  };
  quietHours: {
    enabled: boolean;
    start: string; // "22:00"
    end: string;   // "08:00"
    timezone: string;
  };
}

async function shouldSendPush(userId: string, category: string): Promise<boolean> {
  const prefs = await getPreferences(userId);

  if (!prefs.push) return false;
  if (!prefs.categories[category]) return false;

  if (prefs.quietHours.enabled) {
    const now = new Date();
    // Check quiet hours...
    if (isQuietHours(now, prefs.quietHours)) return false;
  }

  return true;
}
```

---

## Referencias

- [Firebase Cloud Messaging](https://firebase.google.com/docs/cloud-messaging)
- [Apple Push Notification Service](https://developer.apple.com/documentation/usernotifications)
- [Web Push Protocol](https://web.dev/push-notifications-overview/)
- [web-push npm](https://github.com/web-push-libs/web-push)

---

*Skill creada: 2026-02-01*
*Versión: 1.0.0*
