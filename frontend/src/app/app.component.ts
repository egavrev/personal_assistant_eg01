import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

/**
 * Root component. Holds nothing but the top-level router outlet; all layout
 * lives in the routed components (LoginComponent and ShellComponent).
 */
@Component({
  selector: 'app-root',
  imports: [RouterOutlet],
  templateUrl: './app.component.html',
})
export class AppComponent {}
