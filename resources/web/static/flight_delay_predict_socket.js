// Attach a submit handler to the form
$( "#flight_delay_classification" ).submit(function( event ) {

  // Stop form from submitting normally
  event.preventDefault();

  // Get some values from elements on the page:
  var $form = $( this );
  var url = $form.attr( "action" );

  // Send the data using post
  var posting = $.post(
    url,
    $( "#flight_delay_classification" ).serialize()
  );

  // Submit the form and parse the response
  posting.done(function( data ) {
    var response = JSON.parse(data);
    console.log("[Client] Received response from server:", response);

    // If the response is ok, connect to socket and join the room
    if(response.status == "OK") {
      $( "#result" ).empty().append( "Processing... (waiting for Spark)" );

      // Create socket connection with explicit settings
      var socket = io({
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: Infinity,
        transports: ['websocket', 'polling']
      });

      socket.on('connect', function() {
        console.log("[Socket] Connected to server, joining room:", response.id);
        // Join a room with the uuid so we only receive our message
        socket.emit('join', {uuid: response.id});
      });

      socket.on('connect_error', function(error) {
        console.error("[Socket] Connection error:", error);
      });

      // Listen for prediction messages
      socket.on('prediction', function(msg) {
        console.log("[Socket] Received prediction event:", msg);
        try {
          // If the message has a UUID and it matches our id, render
          if(msg && msg.UUID && msg.UUID == response.id) {
            console.log("[Client] UUID matches, rendering page");
            renderPage(msg);
            socket.disconnect();
          }
          else if(!msg.UUID) {
            // If no UUID present, just render the message
            console.log("[Client] No UUID in message, rendering anyway");
            renderPage(msg);
            socket.disconnect();
          }
          else {
            console.log("[Client] UUID mismatch. Expected:", response.id, "Got:", msg.UUID);
          }
        }
        catch(e) {
          console.error('[Client] Error processing prediction message', e);
        }
      });

      socket.on('error', function(error) {
        console.error('[Socket] Socket error:', error);
        $( "#result" ).empty().append( "Error: " + error );
      });

      socket.on('disconnect', function() {
        console.log('[Socket] Disconnected from server');
      });
    }
    else {
      console.error("[Client] Response status was not OK:", response.status);
      $( "#result" ).empty().append( "Error: " + response.status );
    }
  })
  .fail(function(jqXHR, textStatus, errorThrown) {
    console.error("[Client] POST request failed:", textStatus, errorThrown);
    $( "#result" ).empty().append( "Error sending prediction request: " + textStatus );
  });
});

// Render the response on the page for splits:
// [-float("inf"), -15.0, 0, 30.0, float("inf")]
function renderPage(response) {

  console.log("[renderPage] Processing response:", response);

  var displayMessage;

  if(response.Prediction == 0 || response.Prediction == '0') {
      displayMessage = "Early (15+ Minutes Early)";
  }
  else if(response.Prediction == 1 || response.Prediction == '1') {
      displayMessage = "Slightly Early (0-15 Minute Early)";
  }
  else if(response.Prediction == 2 || response.Prediction == '2') {
      displayMessage = "Slightly Late (0-30 Minute Delay)";
  }
  else if(response.Prediction == 3 || response.Prediction == '3') {
      displayMessage = "Very Late (30+ Minutes Late)";
  }
  else {
    displayMessage = "Prediction value: " + response.Prediction;
  }
  
  console.log("[renderPage] Display message:", displayMessage);

  $( "#result" ).empty().append( displayMessage );
}
