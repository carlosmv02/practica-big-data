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

    // If the response is ok, connect to socket and join the room
    if(response.status == "OK") {
      $( "#result" ).empty().append( "Processing..." );

      var socket = io();

      // Join a room with the uuid so we only receive our message
      socket.emit('join', {uuid: response.id});

      // Listen for prediction messages
      socket.on('prediction', function(msg) {
        try {
          // If the message has a UUID and it matches our id, render
          if(msg && msg.UUID && msg.UUID == response.id) {
            renderPage(msg);
            socket.disconnect();
          }
          else if(!msg.UUID) {
            // If no UUID present, just render the message
            renderPage(msg);
            socket.disconnect();
          }
        }
        catch(e) {
          console.error('Error processing prediction message', e);
        }
      });
    }
  });
});

// Render the response on the page for splits:
// [-float("inf"), -15.0, 0, 30.0, float("inf")]
function renderPage(response) {

  console.log(response);

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
  
  console.log(displayMessage)

  $( "#result" ).empty().append( displayMessage );
}
